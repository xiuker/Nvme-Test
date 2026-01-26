import time
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from chamber_controller import ChamberController
from test_host_manager import TestHostManager
from test_script_parser import TestCommand
from logger import ConsoleLogger, TestResultLogger


class TestProgress:
    def __init__(self):
        self.current_command_index = 0
        self.total_commands = 0
        self.current_cycle = 0
        self.total_cycles = 0
        self.current_test_item = ''
        self.current_temperature = 0.0
        self.hold_time = 0
        self.test_results = {}
        self.ssd_status = {}
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.elapsed_time = 0

    def reset(self):
        self.current_command_index = 0
        self.current_cycle = 0
        self.current_test_item = ''
        self.current_temperature = 0.0
        self.test_results = {}
        self.ssd_status = {}
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.elapsed_time = 0


class TestExecutor:
    def __init__(self, chamber_controller: ChamberController, 
                 host_manager: TestHostManager,
                 console_logger: ConsoleLogger,
                 result_logger: TestResultLogger,
                 config: Dict):
        self.chamber = chamber_controller
        self.host_manager = host_manager
        self.console_logger = console_logger
        self.result_logger = result_logger
        self.config = config
        
        self.progress = TestProgress()
        self.test_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.initial_ssd_info = {}
        self.temperature_monitor_thread = None
        self.stop_temperature_monitor = False
        self.temperature_data = {}
        self.selected_hosts = []
        self.pct_first_cycle_filename = {}
        
        self.progress_callbacks = []
        self.log_callbacks = []

    def add_progress_callback(self, callback: Callable):
        self.progress_callbacks.append(callback)

    def add_log_callback(self, callback: Callable):
        self.log_callbacks.append(callback)

    def set_selected_hosts(self, selected_hosts: List[str]):
        self.selected_hosts = selected_hosts
        self.console_logger.info(f'选择测试主板: {", ".join(selected_hosts)}')
    
    def _get_selected_hosts(self) -> List:
        if not self.selected_hosts or '全部' in self.selected_hosts:
            return self.host_manager.hosts
        
        selected_hosts_list = []
        for host in self.host_manager.hosts:
            if host.name in self.selected_hosts:
                selected_hosts_list.append(host)
        
        return selected_hosts_list

    def _notify_progress(self):
        for callback in self.progress_callbacks:
            callback(self.progress)

    def _notify_log(self, message: str, level: str = 'info'):
        for callback in self.log_callbacks:
            callback(message, level)

    def _check_ssd_consistency(self, current_ssd_info: Dict, test_item: str = 'UNKNOWN') -> bool:
        if not self.initial_ssd_info:
            self.initial_ssd_info = current_ssd_info
            return True
        
        for sn, info in current_ssd_info.items():
            if sn in self.initial_ssd_info:
                initial_info = self.initial_ssd_info[sn]
                if (info.get('MN') != initial_info.get('MN') or 
                    info.get('VID') != initial_info.get('VID') or
                    info.get('DID') != initial_info.get('DID')):
                    self.console_logger.error(f'SSD信息不一致: {sn}')
                    self.result_logger.log_error(sn, 'SSD_INFO_MISMATCH', 
                                               f'初始信息: {initial_info}, 当前信息: {info}', 
                                               self.test_time, test_item=test_item, 
                                               temperature=self.progress.current_temperature)
                    return False
        
        for sn in self.initial_ssd_info:
            if sn not in current_ssd_info and test_item != 'TEMP':
                self.console_logger.warning(f'检测到少盘: {sn}')
                self.result_logger.log_error(sn, 'SSD_MISSING', 
                                               f'初始SSD列表中存在，但当前检测不到: {sn}', 
                                               self.test_time, test_item=test_item, 
                                               temperature=self.progress.current_temperature)
        
        return True

    def _start_temperature_monitor(self, interval: int = 30):
        self.stop_temperature_monitor = False
        self.temperature_data = {}
        
        def monitor():
            while not self.stop_temperature_monitor:
                selected_hosts = self._get_selected_hosts()
                selected_host_names = [host.name for host in selected_hosts]
                all_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for host_name, temps in all_temps.items():
                    for ssd_path, temp in temps.items():
                        key = f'{host_name}_{ssd_path}'
                        if key not in self.temperature_data:
                            self.temperature_data[key] = []
                        self.temperature_data[key].append(f'{timestamp}: {temp}°C')
                
                time.sleep(interval)
        
        self.temperature_monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.temperature_monitor_thread.start()

    def _stop_temperature_monitor(self):
        self.stop_temperature_monitor = True
        if self.temperature_monitor_thread:
            self.temperature_monitor_thread.join(timeout=5)

    def _save_temperature_summary(self, start_temps: Dict, end_temps: Dict, start_time: datetime, end_time: datetime):
        for host_name, temps in end_temps.items():
            for ssd_path, end_temp in temps.items():
                start_temp = start_temps.get(host_name, {}).get(ssd_path, 'N/A')
                key = f'{host_name}_{ssd_path}'
                
                for host in self.host_manager.hosts:
                    if host.name == host_name:
                        ssd_info = host.get_ssd_info(ssd_path)
                        ssd_sn = ssd_info.get('SN', 'unknown')
                        
                        temp_summary = []
                        temp_summary.append(f'测试开始时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
                        temp_summary.append(f'测试结束时间: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
                        temp_summary.append(f'开始温度: {start_temp}°C')
                        temp_summary.append(f'结束温度: {end_temp}°C')
                        if start_temp != 'N/A' and end_temp != 'N/A':
                            temp_change = end_temp - start_temp
                            temp_summary.append(f'温度变化: {temp_change:+.1f}°C')
                        
                        self.result_logger.log_temperature_data(ssd_sn, temp_summary, self.test_time)
                        
                        if key in self.temperature_data:
                            self.result_logger.log_temperature_monitor_data(ssd_sn, self.temperature_data[key], self.test_time)
                        break

    def execute_temp_command(self, command: TestCommand) -> bool:
        temperature = command.params['temperature']
        hold_time = command.params['hold_time']
        
        self.progress.current_test_item = 'TEMP'
        self.progress.current_temperature = temperature
        self._notify_progress()
        
        if not self.chamber:
            self.console_logger.error('温箱控制器未初始化')
            return False
        
        if not self.chamber.serial_conn:
            self.chamber._connect()
            if self.chamber.serial_conn:
                self.console_logger.info('温箱串口已连接')
            else:
                self.console_logger.error('温箱串口连接失败')
                return False
        
        self.console_logger.info(f'执行温度命令: 设定温度{temperature}°C，保温{hold_time}秒')
        self._notify_log(f'设定温度: {temperature}°C, 保温时间: {hold_time}秒')
        
        if not self.chamber.set_temperature(temperature):
            self.console_logger.error('设定温度失败')
            return False
        
        if not self.chamber.wait_for_temperature():
            self.console_logger.error('等待温度达到目标值失败')
            return False
        
        start_hold_time = time.time()
        hold_start = start_hold_time
        
        while time.time() - hold_start < hold_time:
            if not self.progress.is_running:
                return False
            
            remaining = int(hold_time - (time.time() - hold_start))
            self.progress.hold_time = remaining
            self._notify_progress()
            
            time.sleep(1)
        
        self.console_logger.info(f'温度命令执行完成: {temperature}°C')
        return True

    def _run_host_test(self, host, cycle: int, fio_size: str, test_item: str = 'PCT', custom_filename: Optional[Dict[str, str]] = None) -> List:
        results = []
        ssd_list = host.get_ssd_list()
        
        def run_ssd_test(ssd_path):
            ssd_info = host.get_ssd_info(ssd_path)
            ssd_sn = ssd_info.get('SN', 'unknown')
            
            link_status = host.get_ssd_link_status(ssd_path)
            link_info = link_status.get('link', '')
            if 'Speed 8GT/s' not in link_info or 'Width x4' not in link_info:
                self.console_logger.warning(f'SSD链路不是Gen3x4 (Speed 8GT/s, Width x4): {ssd_sn}, 链路状态: {link_status}')
                self.result_logger.log_error(ssd_sn, 'LINK_STATUS_WARNING', 
                                               f'链路状态异常: {link_status}', 
                                               self.test_time, test_item=test_item, 
                                               temperature=self.progress.current_temperature, cycle=cycle)
            
            smart_info = host.get_ssd_smart(ssd_path)
            
            fio_command = (f'fio --ioengine=libaio --bs=1M --iodepth=128 --numjobs=1 '
                                   f'--direct=1 --name=test --rw=write --filename=$i --verify=crc32c '
                                   f'--do_verify=1 --group_reporting --size={fio_size}')
            
            full_fio_command = fio_command.replace('$i', ssd_path)
            self.console_logger.info(f'执行FIO命令: {full_fio_command}')
            
            exit_status, output, error = host.run_fio_test(ssd_path, fio_command)
            
            result_content = f'{test_item}测试结果 - 第{cycle}轮\n'
            result_content += f'测试开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            result_content += f'SSD路径: {ssd_path}\n'
            result_content += f'SSD SN: {ssd_sn}\n'
            result_content += f'SSD链路状态: {link_status.get("link", "N/A")}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'SMART信息:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{smart_info}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'FIO执行命令: {full_fio_command}\n'
            if exit_status != 0:
                result_content += f'退出状态: {exit_status}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'FIO输出:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{output}\n'
            if error:
                result_content += f'\n错误:\n{error}\n'
            
            filename = custom_filename.get(ssd_sn) if custom_filename and ssd_sn in custom_filename else None
            self.result_logger.log_test_result(ssd_sn, test_item, 
                                                   self.progress.current_temperature, 
                                                   result_content, self.test_time, append=True, custom_filename=filename)
            
            if exit_status != 0:
                self.console_logger.error(f'{test_item}测试失败: {ssd_sn}')
                self.result_logger.log_error(ssd_sn, f'{test_item}_TEST_FAILED', 
                                                       f'退出状态: {exit_status}, 错误: {error}', 
                                                       self.test_time, test_item=test_item, 
                                                       temperature=self.progress.current_temperature, cycle=cycle)
            
            return (ssd_path, ssd_sn, exit_status)
        
        with ThreadPoolExecutor(max_workers=len(ssd_list)) as executor:
            future_to_ssd = {executor.submit(run_ssd_test, ssd_path): ssd_path for ssd_path in ssd_list}
            
            for future in as_completed(future_to_ssd):
                try:
                    ssd_path, ssd_sn, exit_status = future.result()
                    results.append((ssd_sn, exit_status))
                except Exception as e:
                    self.console_logger.error(f'SSD测试异常: {e}')
        
        return results

    def _run_host_test_bit(self, host, capacity_percent: int) -> List:
        results = []
        ssd_list = host.get_ssd_list()
        
        def run_ssd_test(ssd_path):
            ssd_info = host.get_ssd_info(ssd_path)
            ssd_sn = ssd_info.get('SN', 'unknown')
            
            link_status = host.get_ssd_link_status(ssd_path)
            link_info = link_status.get('link', '')
            if 'Speed 8GT/s' not in link_info or 'Width x4' not in link_info:
                self.console_logger.warning(f'SSD链路不是Gen3x4 (Speed 8GT/s, Width x4): {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'LINK_STATUS_WARNING', 
                                               f'链路状态异常: {link_status}', 
                                               self.test_time, test_item='BIT', 
                                               temperature=self.progress.current_temperature)
            
            smart_info = host.get_ssd_smart(ssd_path)
            
            fio_command = (f'fio --ioengine=libaio --bs=1M --iodepth=128 --numjobs=1 '
                           f'--direct=1 --name=test --rw=write --filename=$i --verify=crc32c '
                           f'--do_verify=1 --group_reporting --size={capacity_percent}%')
            
            full_fio_command = fio_command.replace('$i', ssd_path)
            self.console_logger.info(f'执行FIO命令: {full_fio_command}')
            
            exit_status, output, error = host.run_fio_test(ssd_path, fio_command)
            
            result_content = f'BIT测试结果\n'
            result_content += f'测试开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            result_content += f'SSD路径: {ssd_path}\n'
            result_content += f'SSD SN: {ssd_sn}\n'
            result_content += f'SSD链路状态: {link_status.get("link", "N/A")}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'SMART信息:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{smart_info}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'测试容量: {capacity_percent}%\n'
            if exit_status != 0:
                result_content += f'退出状态: {exit_status}\n'
            result_content += f'FIO执行命令: {full_fio_command}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'FIO输出:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{output}\n'
            if error:
                result_content += f'\n错误:\n{error}\n'
            
            self.result_logger.log_test_result(ssd_sn, 'BIT', 
                                                   self.progress.current_temperature, 
                                                   result_content, self.test_time)
            
            if exit_status != 0:
                self.console_logger.error(f'BIT测试失败: {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'BIT_TEST_FAILED', 
                                               f'退出状态: {exit_status}, 错误: {error}', 
                                               self.test_time, test_item='BIT', 
                                               temperature=self.progress.current_temperature)
            
            return (ssd_path, ssd_sn, exit_status)
        
        with ThreadPoolExecutor(max_workers=len(ssd_list)) as executor:
            future_to_ssd = {executor.submit(run_ssd_test, ssd_path): ssd_path for ssd_path in ssd_list}
            
            for future in as_completed(future_to_ssd):
                try:
                    ssd_path, ssd_sn, exit_status = future.result()
                    results.append((ssd_sn, exit_status))
                except Exception as e:
                    self.console_logger.error(f'SSD测试异常: {e}')
        
        return results

    def _run_host_test_cttw(self, host) -> List:
        results = []
        ssd_list = host.get_ssd_list()
        
        def run_ssd_test(ssd_path):
            ssd_info = host.get_ssd_info(ssd_path)
            ssd_sn = ssd_info.get('SN', 'unknown')
            
            link_status = host.get_ssd_link_status(ssd_path)
            link_info = link_status.get('link', '')
            if 'Speed 8GT/s' not in link_info or 'Width x4' not in link_info:
                self.console_logger.warning(f'SSD链路不是Gen3x4 (Speed 8GT/s, Width x4): {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'LINK_STATUS_WARNING', 
                                               f'链路状态异常: {link_status}', 
                                               self.test_time, test_item='CTTW', 
                                               temperature=self.progress.current_temperature)
            
            smart_info = host.get_ssd_smart(ssd_path)
            
            fio_command = (f'fio --ioengine=libaio --bs=1M --iodepth=128 --numjobs=1 '
                           f'--direct=1 --name=test --rw=write --filename=$i --verify=crc32c '
                           f'--do_verify=0 --group_reporting --size=100%')
            
            full_fio_command = fio_command.replace('$i', ssd_path)
            self.console_logger.info(f'执行FIO命令: {full_fio_command}')
            
            exit_status, output, error = host.run_fio_test(ssd_path, fio_command)
            
            result_content = f'CTTW测试结果\n'
            result_content += f'测试开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            result_content += f'SSD路径: {ssd_path}\n'
            result_content += f'SSD SN: {ssd_sn}\n'
            result_content += f'SSD链路状态: {link_status.get("link", "N/A")}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'SMART信息:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{smart_info}\n'
            result_content += f'\n{"="*60}\n'
            if exit_status != 0:
                result_content += f'退出状态: {exit_status}\n'
            result_content += f'FIO执行命令: {full_fio_command}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'FIO输出:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{output}\n'
            if error:
                result_content += f'\n错误:\n{error}\n'
            
            self.result_logger.log_test_result(ssd_sn, 'CTTW', 
                                                   self.progress.current_temperature, 
                                                   result_content, self.test_time)
            
            if exit_status != 0:
                self.console_logger.error(f'CTTW测试失败: {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'CTTW_TEST_FAILED', 
                                                   f'退出状态: {exit_status}, 错误: {error}', 
                                                   self.test_time, test_item='CTTW', 
                                                   temperature=self.progress.current_temperature)
            
            return (ssd_sn, exit_status)
        
        with ThreadPoolExecutor(max_workers=len(ssd_list)) as executor:
            futures = {executor.submit(run_ssd_test, ssd_path): ssd_path in ssd_list}
            
            for future in as_completed(futures):
                ssd_path = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.console_logger.error(f'SSD {ssd_path} 测试异常: {e}')
        
        return results

    def _run_host_test_cttr(self, host) -> List:
        results = []
        ssd_list = host.get_ssd_list()
        
        def run_ssd_test(ssd_path):
            ssd_info = host.get_ssd_info(ssd_path)
            ssd_sn = ssd_info.get('SN', 'unknown')
            
            link_status = host.get_ssd_link_status(ssd_path)
            link_info = link_status.get('link', '')
            if 'Speed 8GT/s' not in link_info or 'Width x4' not in link_info:
                self.console_logger.warning(f'SSD链路不是Gen3x4 (Speed 8GT/s, Width x4): {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'LINK_STATUS_WARNING', 
                                               f'链路状态异常: {link_status}', 
                                               self.test_time, test_item='CTTR', 
                                               temperature=self.progress.current_temperature)
            
            smart_info = host.get_ssd_smart(ssd_path)
            
            fio_command = (f'fio --ioengine=libaio --bs=1M --iodepth=128 --numjobs=1 '
                           f'--direct=0 --name=test --rw=read --filename=$i --verify=crc32c '
                           f'--do_verify=1 --group_reporting --size=100%')
            
            full_fio_command = fio_command.replace('$i', ssd_path)
            self.console_logger.info(f'执行FIO命令: {full_fio_command}')
            
            exit_status, output, error = host.run_fio_test(ssd_path, fio_command)
            
            result_content = f'CTTR测试结果\n'
            result_content += f'测试开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            result_content += f'SSD路径: {ssd_path}\n'
            result_content += f'SSD SN: {ssd_sn}\n'
            result_content += f'SSD链路状态: {link_status.get("link", "N/A")}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'SMART信息:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{smart_info}\n'
            result_content += f'\n{"="*60}\n'
            if exit_status != 0:
                result_content += f'退出状态: {exit_status}\n'
            result_content += f'FIO执行命令: {full_fio_command}\n'
            result_content += f'\n{"="*60}\n'
            result_content += f'FIO输出:\n'
            result_content += f'{"="*60}\n'
            result_content += f'{output}\n'
            if error:
                result_content += f'\n错误:\n{error}\n'
            
            self.result_logger.log_test_result(ssd_sn, 'CTTR', 
                                                   self.progress.current_temperature, 
                                                   result_content, self.test_time)
            
            if exit_status != 0:
                self.console_logger.error(f'CTTR测试失败: {ssd_sn}')
                self.result_logger.log_error(ssd_sn, 'CTTR_TEST_FAILED', 
                                                   f'退出状态: {exit_status}, 错误: {error}', 
                                                   self.test_time, test_item='CTTR', 
                                                   temperature=self.progress.current_temperature)
            
            return (ssd_path, ssd_sn, exit_status)
        
        with ThreadPoolExecutor(max_workers=len(ssd_list)) as executor:
            future_to_ssd = {executor.submit(run_ssd_test, ssd_path): ssd_path for ssd_path in ssd_list}
            
            for future in as_completed(future_to_ssd):
                try:
                    ssd_path, ssd_sn, exit_status = future.result()
                    results.append((ssd_path, ssd_sn, exit_status))
                except Exception as e:
                    self.console_logger.error(f'SSD测试异常: {e}')
        
        return results

    def execute_pct_command(self, command: TestCommand) -> bool:
        cycles = command.params['cycles']
        pct_config = self.config.get('pct', {})
        wait_time_after_wol = pct_config.get('wait_time_after_wol', 40)
        wait_time_after_shutdown = pct_config.get('wait_time_after_shutdown', 15)
        fio_size = pct_config.get('fio_size', '1G')
        
        self.progress.total_cycles = cycles
        self.progress.current_test_item = 'PCT'
        self._notify_progress()
        
        self.console_logger.info(f'执行PCT测试: {cycles}轮')
        self._notify_log(f'开始PCT测试: {cycles}轮')
        
        selected_hosts = self._get_selected_hosts()
        
        for cycle in range(1, cycles + 1):
            if not self.progress.is_running:
                return False
            
            self.progress.current_cycle = cycle
            self._notify_progress()
            
            cycle_start_time = datetime.now()
            self.console_logger.info(f'PCT测试第{cycle}/{cycles}轮')
            self.console_logger.info(f'本轮测试开始时间: {cycle_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
            self._notify_log(f'PCT测试进度: {cycle}/{cycles}')
            
            self.host_manager.wake_selected_hosts(selected_hosts)
            time.sleep(wait_time_after_wol)
            
            selected_host_names = [host.name for host in selected_hosts]
            if not self.host_manager.wait_all_hosts_online(selected_hosts=selected_host_names):
                self.console_logger.error('等待主机上线超时')
                return False
            
            if not self.host_manager.connect_all_hosts(selected_hosts=selected_host_names):
                self.console_logger.error('连接主机失败')
                return False
            
            current_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
            
            if not self._check_ssd_consistency(current_ssd_info, test_item='PCT'):
                self.console_logger.error('SSD信息一致性检查失败')
                self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
                return False
            
            if cycle == 1:
                for host_name, ssd_dict in current_ssd_info.items():
                    for ssd_path, ssd_info in ssd_dict.items():
                        ssd_sn = ssd_info.get('SN', 'unknown')
                        file_time = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f'{file_time}-{ssd_sn}-PCT-{self.progress.current_temperature}C.txt'
                        self.pct_first_cycle_filename[ssd_sn] = filename
            
            with ThreadPoolExecutor(max_workers=len(selected_hosts)) as executor:
                futures = {executor.submit(self._run_host_test, host, cycle, fio_size, 'PCT', self.pct_first_cycle_filename): host for host in selected_hosts}
                
                for future in as_completed(futures):
                    host = futures[future]
                    try:
                        results = future.result()
                        self.console_logger.info(f'{host.name} 测试完成')
                    except Exception as e:
                        self.console_logger.error(f'{host.name} 测试异常: {e}')
            
            selected_host_names = [host.name for host in selected_hosts]
            self.host_manager.shutdown_all_hosts(selected_hosts=selected_host_names)
            self.console_logger.info(f'已发送关机命令到: {", ".join(selected_host_names)}')
            time.sleep(wait_time_after_shutdown)
            
            if not self.host_manager.wait_all_hosts_shutdown(selected_hosts=selected_host_names):
                self.console_logger.warning('等待主机关机超时')
            
            self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
            
            cycle_end_time = datetime.now()
            cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
            self.console_logger.info(f'本轮测试结束时间: {cycle_end_time.strftime("%Y-%m-%d %H:%M:%S")}')
            self.console_logger.info(f'本轮测试耗时: {cycle_duration:.2f}秒')
            
            cycle_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
            for host_name, ssd_dict in cycle_ssd_info.items():
                for ssd_path, ssd_info in ssd_dict.items():
                    ssd_sn = ssd_info.get('SN', 'unknown')
                    
                    summary_content = f'\n{"="*60}\n'
                    summary_content += f'第{cycle}轮测试总结\n'
                    summary_content += f'测试结束时间: {cycle_end_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                    summary_content += f'本轮测试耗时: {cycle_duration:.2f}秒\n'
                    summary_content += f'{"="*60}\n'
                    
                    filename = self.pct_first_cycle_filename.get(ssd_sn) if ssd_sn in self.pct_first_cycle_filename else None
                    self.result_logger.log_test_result(ssd_sn, 'PCT', 
                                                           self.progress.current_temperature, 
                                                           summary_content, self.test_time, append=True, custom_filename=filename)
        
        self.console_logger.info(f'PCT测试完成: {cycles}轮')
        self._notify_log(f'PCT测试完成: {cycles}轮')
        return True

    def execute_bit_command(self, command: TestCommand) -> bool:
        capacity_percent = command.params['capacity_percent']
        bit_config = self.config.get('bit', {})
        temp_check_interval = bit_config.get('temperature_check_interval', 30)
        
        self.progress.current_test_item = 'BIT'
        self._notify_progress()
        
        self.console_logger.info(f'执行BIT测试: {capacity_percent}%容量')
        self._notify_log(f'开始BIT测试: {capacity_percent}%容量')
        
        test_start_time = datetime.now()
        self.console_logger.info(f'测试开始时间: {test_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        
        selected_hosts = self._get_selected_hosts()
        self.host_manager.wake_selected_hosts(selected_hosts)
        time.sleep(40)
        
        selected_host_names = [host.name for host in selected_hosts]
        if not self.host_manager.wait_all_hosts_online(selected_hosts=selected_host_names):
            self.console_logger.error('等待主机上线超时')
            return False
        
        if not self.host_manager.connect_all_hosts(selected_hosts=selected_host_names):
            self.console_logger.error('连接主机失败')
            return False
        
        current_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        if not self._check_ssd_consistency(current_ssd_info, test_item='BIT'):
            self.console_logger.error('SSD信息一致性检查失败')
            self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
            return False
        
        start_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        self._start_temperature_monitor(temp_check_interval)
        
        bit_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        with ThreadPoolExecutor(max_workers=len(selected_hosts)) as executor:
            futures = {executor.submit(self._run_host_test_bit, host, capacity_percent): host for host in selected_hosts}
            
            for future in as_completed(futures):
                host = futures[future]
                try:
                    results = future.result()
                    self.console_logger.info(f'{host.name} 测试完成')
                except Exception as e:
                    self.console_logger.error(f'{host.name} 测试异常: {e}')
        
        self._stop_temperature_monitor()
        end_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        test_end_time = datetime.now()
        self._save_temperature_summary(start_temps, end_temps, test_start_time, test_end_time)
        
        selected_host_names = [host.name for host in selected_hosts]
        self.host_manager.shutdown_all_hosts(selected_hosts=selected_host_names)
        time.sleep(15)
        
        if not self.host_manager.wait_all_hosts_shutdown(selected_hosts=selected_host_names):
            self.console_logger.warning('等待主机关机超时')
        
        self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
        
        test_duration = (test_end_time - test_start_time).total_seconds()
        self.console_logger.info(f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.console_logger.info(f'测试总耗时: {test_duration:.2f}秒')
        
        for host_name, ssd_dict in bit_ssd_info.items():
            for ssd_path, ssd_info in ssd_dict.items():
                ssd_sn = ssd_info.get('SN', 'unknown')
                
                summary_content = f'\n{"="*60}\n'
                summary_content += f'BIT测试总结\n'
                summary_content += f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                summary_content += f'测试总耗时: {test_duration:.2f}秒\n'
                summary_content += f'{"="*60}\n'
                
                self.result_logger.log_test_result(ssd_sn, 'BIT', 
                                                   self.progress.current_temperature, 
                                                   summary_content, self.test_time, append=True)
        
        self.console_logger.info('BIT测试完成')
        self._notify_log('BIT测试完成')
        return True

    def execute_cttw_command(self, command: TestCommand) -> bool:
        cttw_config = self.config.get('cttw', {})
        temp_check_interval = cttw_config.get('temperature_check_interval', 30)
        
        self.progress.current_test_item = 'CTTW'
        self._notify_progress()
        
        self.console_logger.info('执行CTTW测试: 全盘写测试')
        self._notify_log('开始CTTW测试: 全盘写测试')
        
        test_start_time = datetime.now()
        self.console_logger.info(f'测试开始时间: {test_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        
        selected_hosts = self._get_selected_hosts()
        self.host_manager.wake_selected_hosts(selected_hosts)
        time.sleep(40)
        
        selected_host_names = [host.name for host in selected_hosts]
        if not self.host_manager.wait_all_hosts_online(selected_hosts=selected_host_names):
            self.console_logger.error('等待主机上线超时')
            return False
        
        if not self.host_manager.connect_all_hosts(selected_hosts=selected_host_names):
            self.console_logger.error('连接主机失败')
            return False
        
        current_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        if not self._check_ssd_consistency(current_ssd_info, test_item='CTTW'):
            self.console_logger.error('SSD信息一致性检查失败')
            self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
            return False
        
        start_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        self._start_temperature_monitor(temp_check_interval)
        
        cttw_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        with ThreadPoolExecutor(max_workers=len(selected_hosts)) as executor:
            futures = {executor.submit(self._run_host_test_cttw, host): host for host in selected_hosts}
            
            for future in as_completed(futures):
                host = futures[future]
                try:
                    results = future.result()
                    self.console_logger.info(f'{host.name} 测试完成')
                except Exception as e:
                    self.console_logger.error(f'{host.name} 测试异常: {e}')
        
        self._stop_temperature_monitor()
        end_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        test_end_time = datetime.now()
        self._save_temperature_summary(start_temps, end_temps, test_start_time, test_end_time)
        
        selected_host_names = [host.name for host in selected_hosts]
        self.host_manager.shutdown_all_hosts(selected_hosts=selected_host_names)
        time.sleep(15)
        
        if not self.host_manager.wait_all_hosts_shutdown(selected_hosts=selected_host_names):
            self.console_logger.warning('等待主机关机超时')
        
        self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
        
        test_duration = (test_end_time - test_start_time).total_seconds()
        self.console_logger.info(f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.console_logger.info(f'测试总耗时: {test_duration:.2f}秒')
        
        for host_name, ssd_dict in cttw_ssd_info.items():
            for ssd_path, ssd_info in ssd_dict.items():
                ssd_sn = ssd_info.get('SN', 'unknown')
                
                summary_content = f'\n{"="*60}\n'
                summary_content += f'CTTW测试总结\n'
                summary_content += f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                summary_content += f'测试总耗时: {test_duration:.2f}秒\n'
                summary_content += f'{"="*60}\n'
                
                self.result_logger.log_test_result(ssd_sn, 'CTTW', 
                                                   self.progress.current_temperature, 
                                                   summary_content, self.test_time, append=True)
        
        self.console_logger.info('CTTW测试完成')
        self._notify_log('CTTW测试完成')
        return True

    def execute_cttr_command(self, command: TestCommand) -> bool:
        cttr_config = self.config.get('cttr', {})
        temp_check_interval = cttr_config.get('temperature_check_interval', 30)
        
        self.progress.current_test_item = 'CTTR'
        self._notify_progress()
        
        self.console_logger.info('执行CTTR测试: 全盘读测试')
        self._notify_log('开始CTTR测试: 全盘读测试')
        
        test_start_time = datetime.now()
        self.console_logger.info(f'测试开始时间: {test_start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        
        selected_hosts = self._get_selected_hosts()
        self.host_manager.wake_selected_hosts(selected_hosts)
        time.sleep(40)
        
        selected_host_names = [host.name for host in selected_hosts]
        if not self.host_manager.wait_all_hosts_online(selected_hosts=selected_host_names):
            self.console_logger.error('等待主机上线超时')
            return False
        
        if not self.host_manager.connect_all_hosts(selected_hosts=selected_host_names):
            self.console_logger.error('连接主机失败')
            return False
        
        current_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        if not self._check_ssd_consistency(current_ssd_info, test_item='CTTR'):
            self.console_logger.error('SSD信息一致性检查失败')
            self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
            return False
        
        start_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        self._start_temperature_monitor(temp_check_interval)
        
        cttr_ssd_info = self.host_manager.get_all_ssd_info(selected_hosts=selected_host_names)
        
        with ThreadPoolExecutor(max_workers=len(selected_hosts)) as executor:
            futures = {executor.submit(self._run_host_test_cttr, host): host for host in selected_hosts}
            
            for future in as_completed(futures):
                host = futures[future]
                try:
                    results = future.result()
                    self.console_logger.info(f'{host.name} 测试完成')
                except Exception as e:
                    self.console_logger.error(f'{host.name} 测试异常: {e}')
        
        self._stop_temperature_monitor()
        end_temps = self.host_manager.get_all_ssd_temperatures(selected_hosts=selected_host_names)
        test_end_time = datetime.now()
        self._save_temperature_summary(start_temps, end_temps, test_start_time, test_end_time)
        
        selected_host_names = [host.name for host in selected_hosts]
        self.host_manager.shutdown_all_hosts(selected_hosts=selected_host_names)
        time.sleep(15)
        
        if not self.host_manager.wait_all_hosts_shutdown(selected_hosts=selected_host_names):
            self.console_logger.warning('等待主机关机超时')
        
        self.host_manager.disconnect_all_hosts(selected_hosts=selected_host_names)
        
        test_duration = (test_end_time - test_start_time).total_seconds()
        self.console_logger.info(f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}')
        self.console_logger.info(f'测试总耗时: {test_duration:.2f}秒')
        
        for host_name, ssd_dict in cttr_ssd_info.items():
            for ssd_path, ssd_info in ssd_dict.items():
                ssd_sn = ssd_info.get('SN', 'unknown')
                
                summary_content = f'\n{"="*60}\n'
                summary_content += f'CTTR测试总结\n'
                summary_content += f'测试结束时间: {test_end_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                summary_content += f'测试总耗时: {test_duration:.2f}秒\n'
                summary_content += f'{"="*60}\n'
                
                self.result_logger.log_test_result(ssd_sn, 'CTTR', 
                                                   self.progress.current_temperature, 
                                                   summary_content, self.test_time, append=True)
        
        self.console_logger.info('CTTR测试完成')
        self._notify_log('CTTR测试完成')
        return True

    def execute_commands(self, commands) -> bool:
        self.progress.reset()
        self.progress.total_commands = len(commands)
        self.progress.is_running = True
        self.progress.start_time = time.time()
        
        self.console_logger.info(f'开始执行测试脚本，共{len(commands)}条命令')
        self._notify_log(f'开始执行测试脚本，共{len(commands)}条命令')
        
        for i, command in enumerate(commands):
            if not self.progress.is_running:
                self.console_logger.info('测试已停止')
                break
            
            self.progress.current_command_index = i + 1
            self._notify_progress()
            
            success = False
            
            if command.command_type == 'TEMP':
                success = self.execute_temp_command(command)
            elif command.command_type == 'PCT':
                success = self.execute_pct_command(command)
            elif command.command_type == 'BIT':
                success = self.execute_bit_command(command)
            elif command.command_type == 'CTTW':
                success = self.execute_cttw_command(command)
            elif command.command_type == 'CTTR':
                success = self.execute_cttr_command(command)
            
            if not success:
                self.console_logger.error(f'命令执行失败: {command}')
                self._notify_log(f'命令执行失败: {command}', 'error')
                return False
        
        self.progress.is_running = False
        self.console_logger.info('测试脚本执行完成')
        self._notify_log('测试脚本执行完成')
        return True

    def stop_test(self):
        self.progress.is_running = False
        self.console_logger.info('测试停止信号已发送')
        self._notify_log('测试停止', 'warning')

    def pause_test(self):
        self.progress.is_paused = True
        self.console_logger.info('测试已暂停')
        self._notify_log('测试已暂停', 'warning')

    def resume_test(self):
        self.progress.is_paused = False
        self.console_logger.info('测试已恢复')
        self._notify_log('测试已恢复')
