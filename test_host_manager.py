import paramiko
import time
import socket
from typing import Optional, List, Dict, Tuple
from logger import ConsoleLogger


class TestHost:
    def __init__(self, ip: str, mac: str, name: str, username: str = 'root', 
                 password: str = '1', port: int = 22, connect_timeout: int = 30, 
                 command_timeout: int = 300, logger: Optional[ConsoleLogger] = None):
        self.ip = ip
        self.mac = mac
        self.name = name
        self.username = username
        self.password = password
        self.port = port
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        self.logger = logger
        self.ssh_client = None
        self.ssd_list = []
        self.ssd_info = {}

    def is_online(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.ip, 22))
            sock.close()
            return result == 0
        except Exception:
            return False

    def connect(self) -> bool:
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.connect_timeout
            )
            if self.logger:
                self.logger.info(f'连接测试主机成功: {self.name} ({self.ip})')
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f'连接测试主机失败 {self.name} ({self.ip}): {e}')
            return False

    def disconnect(self):
        if self.ssh_client:
            self.ssh_client.close()
            if self.logger:
                self.logger.info(f'断开测试主机连接: {self.name}')

    def execute_command(self, command: str, timeout: Optional[int] = None) -> Tuple[int, str, str]:
        if timeout is None:
            timeout = self.command_timeout
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            return exit_status, output, error
        except Exception as e:
            if self.logger:
                self.logger.error(f'执行命令失败 [{self.name}]: {command}, 错误: {e}')
            return -1, '', str(e)

    def get_ssd_list(self) -> List[str]:
        exit_status, output, error = self.execute_command('ls /dev/nvme*')
        
        if exit_status == 0:
            ssds = [line.strip() for line in output.split('\n') if line.strip().startswith('/dev/nvme') and 'n' in line]
            self.ssd_list = list(set(ssds))
            if self.logger:
                self.logger.info(f'获取SSD列表成功 [{self.name}]: {self.ssd_list}')
            return self.ssd_list
        else:
            if self.logger:
                self.logger.error(f'获取SSD列表失败 [{self.name}]: {error}')
            return []

    def get_ssd_info(self, ssd_path: str) -> Dict[str, str]:
        info = {}
        
        exit_status, output, error = self.execute_command(f'nvme id-ctrl {ssd_path}')
        
        if exit_status == 0:
            lines = output.split('\n')
            for line in lines:
                if 'mn' in line.lower() or 'model number' in line.lower():
                    info['MN'] = line.split(':')[-1].strip()
                elif 'sn' in line.lower() or 'serial number' in line.lower():
                    info['SN'] = line.split(':')[-1].strip()
                elif 'vid' in line.lower():
                    info['VID'] = line.split(':')[-1].strip()
                elif 'did' in line.lower():
                    info['DID'] = line.split(':')[-1].strip()
        
        if self.logger:
            self.logger.info(f'获取SSD信息成功 [{self.name}] {ssd_path}: {info}')
        return info

    def get_ssd_link_status(self, ssd_path: str) -> Dict[str, str]:
        link_info = {}
        
        exit_status, output, error = self.execute_command(f'nvme list {ssd_path}')
        
        if exit_status == 0:
            lines = output.split('\n')
            for line in lines:
                if 'gen' in line.lower():
                    link_info['link'] = line.strip()
        
        exit_status, output, error = self.execute_command(f'nvme get-feature -f 0x13 {ssd_path}')
        
        if exit_status == 0:
            if 'gen3' in output.lower() or '3' in output:
                link_info['speed'] = 'Gen3'
            elif 'gen4' in output.lower() or '4' in output:
                link_info['speed'] = 'Gen4'
        
        if self.logger:
            self.logger.info(f'获取SSD链路状态成功 [{self.name}] {ssd_path}: {link_info}')
        return link_info

    def get_ssd_smart(self, ssd_path: str) -> str:
        exit_status, output, error = self.execute_command(f'nvme smart-log {ssd_path}')
        
        if exit_status == 0:
            if self.logger:
                self.logger.info(f'获取SSD SMART信息成功 [{self.name}] {ssd_path}')
            return output
        else:
            if self.logger:
                self.logger.error(f'获取SSD SMART信息失败 [{self.name}] {ssd_path}: {error}')
            return ''

    def get_ssd_temperature(self, ssd_path: str) -> Optional[float]:
        exit_status, output, error = self.execute_command(f'nvme smart-log {ssd_path} | grep temperature')
        
        if exit_status == 0:
            try:
                temp_str = output.split(':')[-1].strip()
                temperature = float(temp_str.split()[0])
                return temperature
            except Exception as e:
                if self.logger:
                    self.logger.error(f'解析SSD温度失败 [{self.name}] {ssd_path}: {e}')
        
        return None

    def run_fio_test(self, ssd_path: str, fio_command: str) -> Tuple[int, str, str]:
        full_command = fio_command.replace('$i', ssd_path)
        return self.execute_command(full_command)

    def shutdown(self) -> bool:
        exit_status, output, error = self.execute_command('shutdown -h now', timeout=5)
        
        if exit_status == 0 or 'shutdown' in output.lower():
            if self.logger:
                self.logger.info(f'发送关机命令成功 [{self.name}]')
            return True
        else:
            if self.logger:
                self.logger.error(f'发送关机命令失败 [{self.name}]: {error}')
            return False

    def is_shutdown(self) -> bool:
        return not self.is_online()


class WakeOnLAN:
    @staticmethod
    def send_wol(mac_address: str, ip_address: str = '255.255.255.255', port: int = 9) -> bool:
        try:
            mac_address = mac_address.replace('-', ':').replace('.', ':')
            mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
            
            payload = b'\xff' * 6 + mac_bytes * 16
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, (ip_address, port))
            sock.close()
            
            return True
        except Exception as e:
            print(f'发送WOL命令失败: {e}')
            return False


class TestHostManager:
    def __init__(self, hosts_config, logger: Optional[ConsoleLogger] = None):
        self.hosts = []
        self.logger = logger
        self._init_hosts(hosts_config)

    def _init_hosts(self, hosts_config):
        for config in hosts_config:
            host = TestHost(
                ip=config['ip'],
                mac=config['mac'],
                name=config['name'],
                username=config.get('username', 'root'),
                password=config.get('password', '1'),
                port=config.get('port', 22),
                connect_timeout=config.get('connect_timeout', 30),
                command_timeout=config.get('command_timeout', 300),
                logger=self.logger
            )
            self.hosts.append(host)

    def wake_all_hosts(self):
        for host in self.hosts:
            success = WakeOnLAN.send_wol(host.mac)
            if success:
                if self.logger:
                    self.logger.info(f'发送WOL命令成功: {host.name}')
            else:
                if self.logger:
                    self.logger.error(f'发送WOL命令失败: {host.name}')

    def wait_all_hosts_online(self, wait_time: int = 40, check_interval: int = 2) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < wait_time:
            all_online = all(host.is_online() for host in self.hosts)
            if all_online:
                if self.logger:
                    self.logger.info('所有测试主机已上线')
                return True
            time.sleep(check_interval)
        
        if self.logger:
            self.logger.warning('部分测试主机未在指定时间内上线')
        return False

    def connect_all_hosts(self) -> bool:
        all_connected = True
        for host in self.hosts:
            if not host.connect():
                all_connected = False
        
        return all_connected

    def disconnect_all_hosts(self):
        for host in self.hosts:
            host.disconnect()

    def shutdown_all_hosts(self) -> bool:
        all_shutdown = True
        for host in self.hosts:
            if not host.shutdown():
                all_shutdown = False
        
        return all_shutdown

    def wait_all_hosts_shutdown(self, wait_time: int = 15, check_interval: int = 2) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < wait_time:
            all_shutdown = all(host.is_shutdown() for host in self.hosts)
            if all_shutdown:
                if self.logger:
                    self.logger.info('所有测试主机已关机')
                return True
            time.sleep(check_interval)
        
        if self.logger:
            self.logger.warning('部分测试主机未在指定时间内关机')
        return False

    def get_all_ssd_info(self) -> Dict[str, Dict]:
        all_ssd_info = {}
        for host in self.hosts:
            ssd_list = host.get_ssd_list()
            for ssd_path in ssd_list:
                ssd_info = host.get_ssd_info(ssd_path)
                ssd_sn = ssd_info.get('SN', 'unknown')
                ssd_info['host'] = host.name
                ssd_info['path'] = ssd_path
                all_ssd_info[ssd_sn] = ssd_info
        return all_ssd_info

    def get_all_ssd_temperatures(self) -> Dict[str, Dict[str, float]]:
        all_temps = {}
        for host in self.hosts:
            ssd_list = host.get_ssd_list()
            host_temps = {}
            for ssd_path in ssd_list:
                temp = host.get_ssd_temperature(ssd_path)
                if temp is not None:
                    host_temps[ssd_path] = temp
            all_temps[host.name] = host_temps
        return all_temps
