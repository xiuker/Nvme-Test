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

    def connect(self, retry_count: int = 3, retry_delay: int = 2) -> bool:
        for attempt in range(1, retry_count + 1):
            try:
                if self.logger:
                    self.logger.info(f'尝试连接测试主机 (第{attempt}/{retry_count}次): {self.name} ({self.ip}:{self.port})')
                    self.logger.info(f'连接参数: 用户名={self.username}, 超时={self.connect_timeout}秒')
                
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh_client.connect(
                    self.ip,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.connect_timeout,
                    banner_timeout=10,
                    auth_timeout=20
                )
                
                if self.logger:
                    self.logger.info(f'连接测试主机成功: {self.name} ({self.ip})')
                
                return True
                
            except paramiko.AuthenticationException as e:
                if self.logger:
                    self.logger.error(f'SSH认证失败 [{self.name} ({self.ip})] (第{attempt}次): 用户名或密码错误')
                    self.logger.error(f'认证异常详情: {e}')
                
                if attempt < retry_count:
                    if self.logger:
                        self.logger.warning(f'{retry_delay}秒后重试连接...')
                    time.sleep(retry_delay)
                    continue
                else:
                    return False
                    
            except paramiko.SSHException as e:
                if self.logger:
                    self.logger.error(f'SSH连接失败 [{self.name} ({self.ip})] (第{attempt}次): {e}')
                    self.logger.error(f'SSH异常类型: {type(e).__name__}')
                
                if attempt < retry_count:
                    if self.logger:
                        self.logger.warning(f'{retry_delay}秒后重试连接...')
                    time.sleep(retry_delay)
                    continue
                else:
                    return False
                    
            except socket.timeout as e:
                if self.logger:
                    self.logger.error(f'SSH连接超时 [{self.name} ({self.ip})] (第{attempt}次): 在{self.connect_timeout}秒内无法建立连接')
                    self.logger.error(f'超时异常详情: {e}')
                
                if attempt < retry_count:
                    if self.logger:
                        self.logger.warning(f'{retry_delay}秒后重试连接...')
                    time.sleep(retry_delay)
                    continue
                else:
                    return False
                    
            except ConnectionRefusedError as e:
                if self.logger:
                    self.logger.error(f'连接被拒绝 [{self.name} ({self.ip})] (第{attempt}次): SSH服务可能未启动或端口{self.port}未开放')
                    self.logger.error(f'连接拒绝异常详情: {e}')
                
                if attempt < retry_count:
                    if self.logger:
                        self.logger.warning(f'{retry_delay}秒后重试连接...')
                    time.sleep(retry_delay)
                    continue
                else:
                    return False
                    
            except Exception as e:
                if self.logger:
                    self.logger.error(f'连接测试主机失败 [{self.name} ({self.ip})] (第{attempt}次): {e}')
                    self.logger.error(f'异常类型: {type(e).__name__}')
                    self.logger.error(f'异常详情: {str(e)}')
                
                if attempt < retry_count:
                    if self.logger:
                        self.logger.warning(f'{retry_delay}秒后重试连接...')
                    time.sleep(retry_delay)
                    continue
                else:
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
        if not self.ssh_client:
            if self.logger:
                self.logger.warning(f'SSH未连接，无法获取SSD列表 [{self.name}]')
            return []
        
        exit_status, output, error = self.execute_command('ls /dev/nvme*n1')
        
        if exit_status == 0:
            ssds = [line.strip() for line in output.split('\n') 
                    if line.strip().startswith('/dev/nvme') 
                    and 'n1' in line]
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
        
        try:
            print(f"[DEBUG] get_ssd_link_status 开始执行: {self.name}, {ssd_path}")
            exit_status, output, error = self.execute_command(f'lspci -vvv -d ::0108')
            
            print(f"[DEBUG] 执行命令结果: exit_status={exit_status}, output长度={len(output) if output else 0}, error={error}")
            
            if exit_status == 0:
                lines = output.split('\n')
                print(f"[DEBUG] 输出行数: {len(lines)}")
                for i, line in enumerate(lines):
                    if 'LnkSta:' in line:
                        print(f"[DEBUG] 找到LnkSta行 ({i}): {line.strip()}")
                        link_info['link'] = line.strip()
                        break
            else:
                print(f"[DEBUG] 命令执行失败: {error}")
        except Exception as e:
            print(f"[DEBUG] 异常: {e}")
            if self.logger:
                self.logger.warning(f'获取SSD链路状态失败 [{self.name}] {ssd_path}: {e}')
        
        print(f"[DEBUG] 最终link_info: {link_info}, 类型: {type(link_info).__name__}")
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
        if not self.ssh_client:
            if not self.connect():
                return False
        
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
            host = None
            host_name = config.get('name', 'unknown')
            try:
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
            except Exception as e:
                if self.logger:
                    self.logger.error(f'创建测试主机失败 [{host_name}]: {e}')
            
            if host is not None:
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
    
    def wake_selected_hosts(self, selected_hosts: List):
        for host in selected_hosts:
            if isinstance(host, str):
                host_name = host
                for h in self.hosts:
                    if h.name == host_name:
                        success = WakeOnLAN.send_wol(h.mac)
                        if success:
                            if self.logger:
                                self.logger.info(f'发送WOL命令成功: {host_name}')
                        else:
                            if self.logger:
                                self.logger.error(f'发送WOL命令失败: {host_name}')
                        break
            else:
                success = WakeOnLAN.send_wol(host.mac)
                if success:
                    if self.logger:
                        self.logger.info(f'发送WOL命令成功: {host.name}')
                else:
                    if self.logger:
                        self.logger.error(f'发送WOL命令失败: {host.name}')
    
    def wait_all_hosts_online(self, wait_time: int = 40, check_interval: int = 2, 
                          selected_hosts: Optional[List] = None) -> bool:
        start_time = time.time()
        
        if selected_hosts is None:
            hosts_to_check = self.hosts
        else:
            hosts_to_check = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_check.append(host)
        
        if self.logger:
            self.logger.info(f'开始等待主机上线，超时时间: {wait_time}秒，检查间隔: {check_interval}秒')
            self.logger.info(f'等待主机列表: {[f"{host.name}({host.ip})" for host in hosts_to_check]}')
        
        while time.time() - start_time < wait_time:
            online_hosts = []
            offline_hosts = []
            
            for host in hosts_to_check:
                is_online = host.is_online()
                if is_online:
                    online_hosts.append(host.name)
                else:
                    offline_hosts.append(host.name)
            
            all_online = all(host.is_online() for host in hosts_to_check)
            
            if self.logger:
                self.logger.info(f'主机状态检查 - 在线: {online_hosts}, 离线: {offline_hosts}')
            
            if all_online:
                if self.logger:
                    self.logger.info('所有选中的测试主机已上线')
                return True
            
            time.sleep(check_interval)
        
        if self.logger:
            self.logger.warning(f'等待主机上线超时，超时时间: {wait_time}秒')
            self.logger.warning(f'仍未上线的主机: {offline_hosts}')
            self.logger.warning(f'请检查:')
            self.logger.warning(f'  1. 主机是否已开机')
            self.logger.warning(f'  2. Wake-on-LAN是否生效')
            self.logger.warning(f'  3. 网络连接是否正常')
            self.logger.warning(f'  4. SSH服务是否已启动')
        
        return False

    def connect_all_hosts(self, selected_hosts: Optional[List] = None) -> bool:
        if selected_hosts is None:
            hosts_to_connect = self.hosts
        else:
            hosts_to_connect = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_connect.append(host)
        
        all_connected = True
        
        if self.logger:
            self.logger.info(f'开始连接主机，共{len(hosts_to_connect)}台')
            self.logger.info(f'连接主机列表: {[f"{host.name}({host.ip})" for host in hosts_to_connect]}')
        
        for host in hosts_to_connect:
            if self.logger:
                self.logger.info(f'正在连接主机: {host.name} ({host.ip})')
            
            if not host.connect():
                all_connected = False
                if self.logger:
                    self.logger.error(f'主机连接失败: {host.name} ({host.ip})')
            else:
                if self.logger:
                    self.logger.info(f'主机连接成功: {host.name} ({host.ip})')
        
        if all_connected:
            if self.logger:
                self.logger.info('所有选中的测试主机连接成功')
        else:
            if self.logger:
                self.logger.error('部分或全部选中的测试主机连接失败')
        
        return all_connected

    def disconnect_all_hosts(self, selected_hosts: Optional[List] = None):
        if selected_hosts is None:
            hosts_to_disconnect = self.hosts
        else:
            hosts_to_disconnect = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_disconnect.append(host)
        
        for host in hosts_to_disconnect:
            host.disconnect()

    def shutdown_all_hosts(self, selected_hosts: Optional[List] = None) -> bool:
        if selected_hosts is None:
            hosts_to_shutdown = self.hosts
        else:
            hosts_to_shutdown = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_shutdown.append(host)
        
        all_shutdown = True
        
        if self.logger:
            self.logger.info(f'开始关机，共{len(hosts_to_shutdown)}台')
            self.logger.info(f'关机主机列表: {[host.name for host in hosts_to_shutdown]}')
        
        for host in hosts_to_shutdown:
            if not host.shutdown():
                all_shutdown = False
                if self.logger:
                    self.logger.error(f'主机关机失败: {host.name}')
            else:
                if self.logger:
                    self.logger.info(f'主机关机成功: {host.name}')
        
        if all_shutdown:
            if self.logger:
                self.logger.info('所有选中的测试主机已发送关机命令')
        else:
            if self.logger:
                self.logger.error('部分或全部选中的测试主机关机失败')
        
        return all_shutdown

    def wait_all_hosts_shutdown(self, wait_time: int = 15, check_interval: int = 2,
                            selected_hosts: Optional[List] = None) -> bool:
        start_time = time.time()
        
        if selected_hosts is None:
            hosts_to_check = self.hosts
        else:
            hosts_to_check = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_check.append(host)
        
        if self.logger:
            self.logger.info(f'开始等待主机关机，超时时间: {wait_time}秒，检查间隔: {check_interval}秒')
            self.logger.info(f'等待主机列表: {[host.name for host in hosts_to_check]}')
        
        while time.time() - start_time < wait_time:
            online_hosts = []
            shutdown_hosts = []
            
            for host in hosts_to_check:
                is_shutdown = host.is_shutdown()
                if is_shutdown:
                    shutdown_hosts.append(host.name)
                else:
                    online_hosts.append(host.name)
            
            all_shutdown = all(host.is_shutdown() for host in hosts_to_check)
            
            if self.logger:
                self.logger.info(f'主机状态检查 - 已关机: {shutdown_hosts}, 仍在线: {online_hosts}')
            
            if all_shutdown:
                if self.logger:
                    self.logger.info('所有选中的测试主机已关机')
                return True
            
            time.sleep(check_interval)
        
        if self.logger:
            self.logger.warning(f'等待主机关机超时，超时时间: {wait_time}秒')
            self.logger.warning(f'仍未关机的主机: {online_hosts}')
        
        return False

    def get_all_ssd_info(self, selected_hosts: Optional[List] = None, silent: bool = False) -> Dict[str, Dict]:
        if selected_hosts is None:
            hosts_to_check = self.hosts
        else:
            hosts_to_check = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_check.append(host)
        
        all_ssd_info = {}
        
        if self.logger and not silent:
            self.logger.info(f'获取SSD信息，共{len(hosts_to_check)}台主机')
        
        for host in hosts_to_check:
            if not host.ssh_client:
                if self.logger and not silent:
                    self.logger.warning(f'SSH未连接，跳过获取SSD信息 [{host.name}]')
                continue
            
            ssd_list = host.get_ssd_list()
            for ssd_path in ssd_list:
                ssd_info = host.get_ssd_info(ssd_path)
                ssd_sn = ssd_info.get('SN', 'unknown')
                ssd_info['host'] = host.name
                ssd_info['path'] = ssd_path
                all_ssd_info[ssd_sn] = ssd_info
        
        if self.logger and not silent:
            self.logger.info(f'获取SSD信息完成，共{len(all_ssd_info)}个SSD')
        
        return all_ssd_info
    
    def connect_selected_hosts(self, selected_hosts: List[str]) -> bool:
        print(f"[DEBUG] connect_selected_hosts 开始执行")
        print(f"[DEBUG] selected_hosts: {selected_hosts}")
        print(f"[DEBUG] self.hosts数量: {len(self.hosts)}")
        
        all_connected = True
        
        if self.logger:
            self.logger.info(f'开始连接选中的主板，共{len(selected_hosts)}台')
            self.logger.info(f'连接主板列表: {selected_hosts}')
        
        for host in self.hosts:
            print(f"[DEBUG] 检查 host: {host.name}, ip={host.ip}")
            if host.name in selected_hosts:
                print(f"[DEBUG] host {host.name} 在 selected_hosts 中，开始连接")
                if self.logger:
                    self.logger.info(f'正在连接主板: {host.name} ({host.ip}:{host.port})')
                
                success = host.connect(retry_count=3, retry_delay=2)
                print(f"[DEBUG] host {host.name} 连接结果: {success}")
                
                if success:
                    if self.logger:
                        self.logger.info(f'主板连接成功: {host.name}')
                else:
                    if self.logger:
                        self.logger.error(f'主板连接失败: {host.name}')
                    all_connected = False
            else:
                print(f"[DEBUG] host {host.name} 不在 selected_hosts 中，跳过")
        
        if self.logger:
            if all_connected:
                self.logger.info('所有选中的主板连接成功')
            else:
                self.logger.error(f'部分或全部选中的主板连接失败')
        
        print(f"[DEBUG] connect_selected_hosts 返回值: {all_connected}")
        return all_connected
    
    def get_selected_ssd_info(self, selected_hosts: List[str]) -> Dict[str, Dict]:
        print(f"[DEBUG] get_selected_ssd_info 开始执行")
        print(f"[DEBUG] selected_hosts: {selected_hosts}")
        print(f"[DEBUG] self.hosts数量: {len(self.hosts)}")
        
        all_ssd_info = {}
        
        if self.logger and not False:
            self.logger.info(f'获取选中的主板SSD信息，共{len(selected_hosts)}台')
        
        for host in self.hosts:
            print(f"[DEBUG] 检查 host: {host.name}, ip={host.ip}")
            if host.name in selected_hosts:
                print(f"[DEBUG] host {host.name} 在 selected_hosts 中")
                if not host.ssh_client:
                    print(f"[DEBUG] host {host.name} SSH未连接")
                    if self.logger:
                        self.logger.warning(f'SSH未连接，跳过获取SSD信息 [{host.name}]')
                    continue
                
                print(f"[DEBUG] host {host.name} SSH已连接，获取SSD列表")
                ssd_list = host.get_ssd_list()
                print(f"[DEBUG] host {host.name} SSD列表: {ssd_list}")
                
                for ssd_path in ssd_list:
                    print(f"[DEBUG] 获取SSD信息: {ssd_path}")
                    ssd_info = host.get_ssd_info(ssd_path)
                    print(f"[DEBUG] SSD info: {ssd_info}")
                    
                    ssd_sn = ssd_info.get('SN', 'unknown')
                    ssd_info['host'] = host.name
                    ssd_info['path'] = ssd_path
                    all_ssd_info[ssd_sn] = ssd_info
                    print(f"[DEBUG] 添加SSD到all_ssd_info: key={ssd_sn}")
            else:
                print(f"[DEBUG] host {host.name} 不在 selected_hosts 中，跳过")
        
        print(f"[DEBUG] all_ssd_info: {all_ssd_info}")
        print(f"[DEBUG] all_ssd_info keys: {list(all_ssd_info.keys())}")
        print(f"[DEBUG] get_selected_ssd_info 返回值: {all_ssd_info}")
        return all_ssd_info

    def get_all_ssd_temperatures(self, selected_hosts: Optional[List] = None) -> Dict[str, Dict[str, float]]:
        if selected_hosts is None:
            hosts_to_check = self.hosts
        else:
            hosts_to_check = []
            for host in self.hosts:
                if host.name in selected_hosts:
                    hosts_to_check.append(host)
        
        all_temps = {}
        for host in hosts_to_check:
            if not host.ssh_client:
                if self.logger:
                    self.logger.warning(f'SSH未连接，跳过获取SSD温度 [{host.name}]')
                continue
            
            ssd_list = host.get_ssd_list()
            host_temps = {}
            for ssd_path in ssd_list:
                temp = host.get_ssd_temperature(ssd_path)
                if temp is not None:
                    host_temps[ssd_path] = temp
            all_temps[host.name] = host_temps
        return all_temps
