import os
import PySimpleGUI as sg
import threading
import time
import atexit
import signal
import sys
from typing import Optional, Dict, List
from datetime import datetime

from logger import ConsoleLogger, TestResultLogger
from chamber_controller import ChamberController
from test_host_manager import TestHostManager
from test_script_parser import TestScriptParser, TestConfigParser
from test_executor import TestExecutor, TestProgress
from test_result_analyzer import TestResultAnalyzer
from html_report_generator import HTMLReportGenerator
from real_time_monitor import RealTimeMonitor
from thread_manager import ThreadPoolManager, ResourceCleaner, MemoryMonitor


class NVMeTestGUI:
    def __init__(self):
        sg.theme('LightGrey1')
        
        self.console_logger = ConsoleLogger()
        self.result_logger = TestResultLogger()
        
        self.config_parser = TestConfigParser('./config.ini', self.console_logger)
        self.config = self._load_config()
        
        self.chamber_controller = None
        self.host_manager = None
        self.test_executor = None
        self.test_analyzer = TestResultAnalyzer(self.config, self.console_logger)
        self.html_generator = HTMLReportGenerator(self.console_logger)
        self.real_time_monitor = RealTimeMonitor(self.console_logger)
        
        self.test_commands = []
        self.test_thread = None
        self.monitor_thread = None
        self.is_monitoring = False
        self.is_testing = False
        self.selected_hosts = []
        
        self.thread_pool = ThreadPoolManager(max_workers=20, logger=self.console_logger)
        self.resource_cleaner = ResourceCleaner()
        self.resource_cleaner.set_logger(self.console_logger)
        self.memory_monitor = MemoryMonitor(logger=self.console_logger)
        
        self._setup_signal_handlers()
        self._setup_exit_handlers()
        
        self.window = self._create_window()
        self.window.maximize()
        
        serial_config = self.config['serial']
        self.window['-CURRENT_COM-'].update(serial_config['port'])
        self.window['-STATUS-'].update('串口状态: 已关闭')
        
        self.console_logger.info('NVMe SSD测试系统启动')
        
        self.memory_monitor.start()

    def _load_config(self) -> Dict:
        config = {
            'serial': self.config_parser.get_serial_config(),
            'chamber': self.config_parser.get_chamber_config(),
            'test_hosts': self.config_parser.get_test_hosts_config(),
            'ssh': self.config_parser.get_ssh_config(),
            'pct': self.config_parser.get_pct_config(),
            'bit': self.config_parser.get_bit_config(),
            'cttw': self.config_parser.get_cttw_config(),
            'cttr': self.config_parser.get_cttr_config(),
            'logging': self.config_parser.get_logging_config(),
            'analysis': self.config_parser.get_analysis_config()
        }
        return config

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_exit_handlers(self):
        atexit.register(self._cleanup_on_exit)

    def _signal_handler(self, signum, frame):
        self.console_logger.info(f'收到信号 {signum}，准备退出...')
        self._cleanup()
        sys.exit(0)

    def _cleanup_on_exit(self):
        self.console_logger.info('程序退出，执行清理...')
        self._cleanup()

    def _cleanup(self):
        try:
            if self.test_thread and self.test_thread.is_alive():
                if self.test_executor:
                    self.test_executor.stop_test()
                self.test_thread.join(timeout=5)
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.is_monitoring = False
                self.monitor_thread.join(timeout=5)
            
            if self.real_time_monitor:
                self.real_time_monitor.stop_monitoring()
            
            if self.memory_monitor:
                self.memory_monitor.stop()
            
            if self.thread_pool:
                self.thread_pool.shutdown(wait=True, timeout=5)
            
            if self.resource_cleaner:
                self.resource_cleaner.cleanup_all()
            
            if self.chamber_controller:
                self.chamber_controller.close()
            
            if self.host_manager:
                self.host_manager.disconnect_all_hosts()
            
            self.console_logger.info('资源清理完成')
        
        except Exception as e:
            self.console_logger.error(f'清理资源时发生错误: {e}')

    def _create_window(self):
        chamber_frame = [
            [sg.Text('当前COM口:', size=(10, 1)), sg.Text('COM18', key='-CURRENT_COM-', size=(8, 1), text_color='dark blue')],
            [sg.Text('温箱温度:', size=(8, 1)), sg.Text('0.0°C', key='-CHAMBER_TEMP-', size=(5, 1), text_color='dark blue'),
             sg.Text('保温倒计时:', size=(12, 1)), sg.Text('0秒', key='-HOLD_TIME-', size=(10, 1), text_color='dark blue')],
            [sg.HSeparator()],
            [sg.Text('设置COM口:', size=(10, 1)), sg.Input(key='-COM_INPUT-', size=(10, 1)), sg.Button('保存', key='-SAVE_COM-', size=(8, 1))],
            [sg.HSeparator()],
            [sg.Button('连接串口', key='-CONNECT_SERIAL-', size=(12, 1)), 
             sg.Button('关闭串口', key='-CLOSE_SERIAL-', size=(12, 1))],
            [sg.HSeparator()],
            [sg.Button('读取温度', key='-READ_TEMP-', size=(12, 1))],
            [sg.Button('设定温度', key='-SET_TEMP-', size=(12, 1)),sg.Input(key='-TEMP_INPUT-', size=(10, 1)), sg.Text('°C')],
            [sg.Button('启动温箱', key='-START_CHAMBER-', size=(12, 1)), 
             sg.Button('停止温箱', key='-STOP_CHAMBER-', size=(12, 1))],
            
            [sg.Checkbox('串口Debug', default=False, key='-CHAMBER_DEBUG-')]
        ]

        test_script_frame = [
            [sg.Text('测试脚本:', size=(10, 1)), 
             sg.Input(key='-SCRIPT_PATH-', size=(30, 1), readonly=True)],
            [sg.Button('选择文件', key='-SELECT_SCRIPT-', size=(10, 1)),
             sg.Button('加载脚本', key='-LOAD_SCRIPT-', size=(10, 1))],
            [sg.Button('预览脚本', key='-PREVIEW_SCRIPT-', size=(10, 1)),
             sg.Button('验证脚本', key='-VALIDATE_SCRIPT-', size=(10, 1))],
            [sg.Text('脚本命令数:', size=(12, 1)), 
             sg.Text('0', key='-COMMAND_COUNT-', size=(5, 1), text_color='dark blue')]
        ]

        test_control_frame = [
            [sg.Text('选择主板:', size=(12, 1))],
            [sg.Checkbox('test_host_1', default=False, key='-CHECK_HOST_1-'),
             sg.Checkbox('test_host_2', default=False, key='-CHECK_HOST_2-')],
            [sg.Checkbox('test_host_3', default=False, key='-CHECK_HOST_3-'),
             sg.Checkbox('test_host_4', default=False, key='-CHECK_HOST_4-')],
            [sg.HSeparator()],
            [sg.Button('主板开机', key='-WAKE_HOSTS-', size=(12, 1), button_color=('black', 'purple')),
             sg.Button('连接主板', key='-CONNECT_HOSTS-', size=(12, 1), button_color=('black', 'blue'))],
            [sg.Button('主板关机', key='-SHUTDOWN_HOSTS-', size=(12, 1), button_color=('black', 'darkred'))],
            [sg.HSeparator()],
            [sg.Button('开始测试', key='-START_TEST-', size=(12, 1), button_color=('black', 'green')),
             sg.Button('暂停测试', key='-PAUSE_TEST-', size=(12, 1), button_color=('black', 'orange')),
             sg.Button('停止测试', key='-STOP_TEST-', size=(12, 1), button_color=('black', 'red'))],
            [sg.HSeparator()],
            [sg.Text('当前命令:', size=(12, 1)), 
             sg.Text('0/0', key='-COMMAND_PROGRESS-', size=(10, 1), text_color='dark blue')],
            [sg.Text('当前测试项:', size=(12, 1)), 
             sg.Text('无', key='-CURRENT_TEST_ITEM-', size=(15, 1), text_color='dark blue')],
            [sg.Text('当前温度:', size=(12, 1)), 
             sg.Text('0.0°C', key='-CURRENT_TEMP-', size=(10, 1), text_color='dark blue')],
            [sg.Text('测试轮次:', size=(12, 1)), 
             sg.Text('0/0', key='-CYCLE_PROGRESS-', size=(10, 1), text_color='dark blue')]
        ]
        
        ssd_info_frame_1 = [
            [sg.Multiline('', key='-SSD_INFO_1-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        ssd_info_frame_2 = [
            [sg.Multiline('', key='-SSD_INFO_2-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        ssd_info_frame_3 = [
            [sg.Multiline('', key='-SSD_INFO_3-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        ssd_info_frame_4 = [
            [sg.Multiline('', key='-SSD_INFO_4-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        host_info_frame_1 = [
            [sg.Multiline('', key='-HOST_INFO_1-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        host_info_frame_2 = [
            [sg.Multiline('', key='-HOST_INFO_2-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        host_info_frame_3 = [
            [sg.Multiline('', key='-HOST_INFO_3-', size=(40, 10), disabled=True, autoscroll=True)]
        ]
        
        host_info_frame_4 = [
            [sg.Multiline('', key='-HOST_INFO_4-', size=(40, 10), disabled=True, autoscroll=True)]
        ]

        monitor_frame = [
            [sg.Text('实时监控日志', size=(20, 1), justification='center')],
            [sg.HSeparator()],
            [sg.Multiline('', key='-MONITOR_LOG-', size=(80, 35), disabled=True, autoscroll=True)]
        ]

        report_frame = [
            [sg.Text('测试报告', size=(20, 1), justification='center')],
            [sg.HSeparator()],
            [sg.Button('生成HTML报告', key='-GENERATE_REPORT-', size=(15, 1)),
             sg.Button('打开报告', key='-OPEN_REPORT-', size=(15, 1))],
            [sg.Text('报告路径:', size=(10, 1)), 
             sg.Input(key='-REPORT_PATH-', size=(30, 1), readonly=True)]
        ]

        left_column = [
            [sg.Frame('测试脚本', test_script_frame, size=(300, 150))],
            [sg.Frame('测试控制', test_control_frame, size=(300, 300))],
            [sg.Frame('测试报告', report_frame, size=(300, 150))]
        ]

        middle_column = [
            [sg.Frame('test_host_1 SSD信息', ssd_info_frame_1, size=(350, 180))],
            [sg.Frame('test_host_2 SSD信息', ssd_info_frame_2, size=(350, 180))],
            [sg.Frame('test_host_3 SSD信息', ssd_info_frame_3, size=(350, 180))],
            [sg.Frame('test_host_4 SSD信息', ssd_info_frame_4, size=(350, 180))]
        ]
        
        right_column = [
            [sg.Frame('test_host_1 主板信息', host_info_frame_1, size=(350, 150))],
            [sg.Frame('test_host_2 主板信息', host_info_frame_2, size=(350, 150))],
            [sg.Frame('test_host_3 主板信息', host_info_frame_3, size=(350, 150))],
            [sg.Frame('test_host_4 主板信息', host_info_frame_4, size=(350, 150))]
        ]

        chamber_tab = [
            [sg.Frame('温箱控制', chamber_frame, size=(400, 300))]
        ]

        test_control_tab = [
            [sg.Column(left_column, element_justification='c'),
             sg.VSeparator(),
             sg.Column(middle_column, element_justification='c'),
             sg.VSeparator(),
             sg.Column(right_column, element_justification='c')]
        ]

        layout = [
            [sg.TabGroup([
                [sg.Tab('温箱控制', chamber_tab)],
                [sg.Tab('测试控制', test_control_tab)],
                [sg.Tab('实时监控', [[sg.Frame('', monitor_frame, size=(1400, 700))]])]
            ], size=(1400, 700))],
            [sg.StatusBar('就绪', key='-STATUS-', size=(80, 1))]
        ]

        return sg.Window('NVMe SSD测试系统', layout, finalize=True, resizable=True, size=(1600, 900))

    def _log_to_monitor(self, message: str, level: str = 'info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f'[{timestamp}] [{level.upper()}] {message}\n'
        
        self.window['-MONITOR_LOG-'].print(log_message, end='')
        
        if level == 'error':
            self.window['-MONITOR_LOG-'].update(background_color='#ffcccc')
        elif level == 'warning':
            self.window['-MONITOR_LOG-'].update(background_color='#ffffcc')
        else:
            self.window['-MONITOR_LOG-'].update(background_color='#ccffcc')

    def _init_chamber_controller(self):
        try:
            serial_config = self.config['serial']
            chamber_config = self.config['chamber']
            
            debug_enabled = self.window['-CHAMBER_DEBUG-'].get() if hasattr(self.window, '-CHAMBER_DEBUG-') else False
            
            self.chamber_controller = ChamberController(
                port=serial_config['port'],
                baudrate=serial_config['baudrate'],
                bytesize=serial_config['bytesize'],
                parity=serial_config['parity'],
                stopbits=serial_config['stopbits'],
                timeout=serial_config['timeout'],
                command_set=chamber_config['command_set'],
                logger=self.console_logger,
                debug=debug_enabled
            )
            return True
        except Exception as e:
            self.console_logger.error(f'初始化温箱控制器失败: {e}')
            self._log_to_monitor(f'初始化温箱控制器失败: {e}', 'error')
            return False

    def _init_host_manager(self):
        try:
            hosts_config = self.config['test_hosts']
            ssh_config = self.config['ssh']
            
            hosts_with_ssh = []
            for host in hosts_config:
                host.update(ssh_config)
                hosts_with_ssh.append(host)
            
            self.host_manager = TestHostManager(hosts_with_ssh, self.console_logger)
            return True
        except Exception as e:
            self.console_logger.error(f'初始化主机管理器失败: {e}')
            self._log_to_monitor(f'初始化主机管理器失败: {e}', 'error')
            return False

    def _init_test_executor(self):
        try:
            has_temp_command = any(cmd.command_type == 'TEMP' for cmd in self.test_commands)
            
            if has_temp_command:
                if not self.chamber_controller:
                    if not self._init_chamber_controller():
                        return False
            else:
                self.chamber_controller = None
            
            if not self.host_manager:
                if not self._init_host_manager():
                    return False
            
            self.test_executor = TestExecutor(
                chamber_controller=self.chamber_controller,
                host_manager=self.host_manager,
                console_logger=self.console_logger,
                result_logger=self.result_logger,
                config=self.config
            )
            
            self.test_executor.add_progress_callback(self._update_progress)
            self.test_executor.add_log_callback(self._log_to_monitor)
            
            return True
        except Exception as e:
            self.console_logger.error(f'初始化测试执行器失败: {e}')
            self._log_to_monitor(f'初始化测试执行器失败: {e}', 'error')
            return False

    def _update_progress(self, progress: TestProgress):
        self.window['-COMMAND_PROGRESS-'].update(f'{progress.current_command_index}/{progress.total_commands}')
        self.window['-CURRENT_TEST_ITEM-'].update(progress.current_test_item)
        self.window['-CURRENT_TEMP-'].update(f'{progress.current_temperature:.1f}°C')
        self.window['-CYCLE_PROGRESS-'].update(f'{progress.current_cycle}/{progress.total_cycles}')
        self.window['-HOLD_TIME-'].update(f'{progress.hold_time}秒')
        
        if progress.is_running:
            self.window['-STATUS-'].update('测试运行中...')
        elif progress.is_paused:
            self.window['-STATUS-'].update('测试已暂停')
        else:
            self.window['-STATUS-'].update('测试停止')

    def _update_ssd_info(self, silent: bool = False):
        if not self.host_manager:
            return
        
        try:
            all_ssd_info = self.host_manager.get_all_ssd_info(silent=silent)
            
            for i, host in enumerate(self.host_manager.hosts, 1):
                info_text = f'主板: {host.name}\n'
                
                host_ssd_count = 0
                for ssd_sn, ssd_info in all_ssd_info.items():
                    if ssd_info.get('host') == host.name and ssd_sn != 'unknown':
                        host_ssd_count += 1
                        info_text += f'SSD SN: {ssd_sn}\n'
                        info_text += f'  路径: {ssd_info.get("path", "N/A")}\n'
                        info_text += '-' * 30 + '\n'
                
                if host_ssd_count == 0:
                    info_text += f'{host.name} 未找到SSD信息\n'
                
                self.window[f'-SSD_INFO_{i}-'].update(info_text)
            
            self.window.refresh()
                
        except Exception as e:
            if not silent:
                self.console_logger.error(f'更新SSD信息失败: {e}')
    
    def _update_host_info(self):
        if not self.host_manager:
            return
        
        try:
            host_info_list = []
            for i, host in enumerate(self.host_manager.hosts, 1):
                host_info_text = f'主板名称: {host.name}\n'
                host_info_text += f'IP地址: {host.ip}\n'
                host_info_text += f'MAC地址: {host.mac}\n'
                host_info_text += f'端口: {host.port}\n'
                host_info_text += f'用户名: {host.username}\n'
                host_info_text += f'连接超时: {host.connect_timeout}秒\n'
                host_info_text += f'命令超时: {host.command_timeout}秒\n'
                
                is_online = host.is_online()
                status = '在线' if is_online else '离线'
                host_info_text += f'状态: {status}\n'
                
                host_info_list.append((i, host_info_text))
            
            for i, host_info_text in host_info_list:
                try:
                    self.window[f'-HOST_INFO_{i}-'].update(host_info_text)
                except:
                    pass
            
            self.window.refresh()
                
        except Exception as e:
            pass
    
    def _update_chamber_debug(self):
        try:
            debug_enabled = self.window['-CHAMBER_DEBUG-'].get()
            
            self.console_logger.debug(f'Debug开关状态: {debug_enabled}')
            
            if self.chamber_controller:
                self.chamber_controller.debug = debug_enabled
                status = '启用' if debug_enabled else '禁用'
                self._log_to_monitor(f'串口Debug已{status}', 'info')
                
                if debug_enabled:
                    self.console_logger.debug('串口Debug已启用，将记录所有串口数据')
                else:
                    self.console_logger.debug('串口Debug已禁用，不记录串口数据')
            else:
                self._log_to_monitor('温箱控制器未初始化', 'warning')
        except Exception as e:
            self.console_logger.error(f'更新串口Debug状态失败: {e}')
    
    def _save_com_port(self):
        try:
            com_port = self.window['-COM_INPUT-'].get().strip()
            
            if not com_port:
                sg.popup_error('请输入COM口号！', title='错误')
                return
            
            if not com_port.upper().startswith('COM'):
                sg.popup_error('COM口号格式错误，应为COM1、COM2等格式！', title='错误')
                return
            
            try:
                com_num = int(com_port[3:])
                if com_num < 1 or com_num > 256:
                    sg.popup_error('COM口号超出范围，应为1-256！', title='错误')
                    return
            except ValueError:
                sg.popup_error('COM口号格式错误，应为COM1、COM2等格式！', title='错误')
                return
            
            config_path = './config.ini'
            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                if line.strip().startswith('port ='):
                    lines[i] = f'port = {com_port.upper()}\n'
                    break
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            self.window['-CURRENT_COM-'].update(com_port.upper())
            self.config['serial']['port'] = com_port.upper()
            
            self._log_to_monitor(f'COM口已保存: {com_port.upper()}', 'info')
            self.console_logger.info(f'COM口已保存到配置文件: {com_port.upper()}')
            
            sg.popup_ok(f'COM口已保存: {com_port.upper()}', title='成功')
            
        except Exception as e:
            self.console_logger.error(f'保存COM口失败: {e}')
            self._log_to_monitor(f'保存COM口失败: {e}', 'error')
            sg.popup_error(f'保存COM口失败: {e}', title='错误')
    
    def _connect_serial(self):
        try:
            if not self.chamber_controller:
                if not self._init_chamber_controller():
                    return
            
            if self.chamber_controller.serial_conn:
                self._log_to_monitor('串口已处于连接状态', 'warning')
                return
            
            self.chamber_controller._connect()
            if self.chamber_controller.serial_conn:
                self._log_to_monitor(f'温箱串口已连接: {self.chamber_controller.port}', 'info')
                self.console_logger.info(f'温箱串口已连接: {self.chamber_controller.port}')
                self.window['-STATUS-'].update(f'串口状态: 已连接({self.chamber_controller.port})')
            else:
                self._log_to_monitor('串口连接失败', 'error')
                self.console_logger.error('串口连接失败')
                self.window['-STATUS-'].update(f'串口状态: 连接失败')
        except Exception as e:
            self.console_logger.error(f'连接串口失败: {e}')
            self._log_to_monitor(f'连接串口失败: {e}', 'error')
            self.window['-STATUS-'].update(f'串口状态: 连接失败')
    
    def _close_serial(self):
        try:
            if not self.chamber_controller:
                self._log_to_monitor('温箱控制器未初始化', 'warning')
                return
            
            if not self.chamber_controller.serial_conn:
                self._log_to_monitor('串口已处于关闭状态', 'warning')
                return
            
            self.chamber_controller._disconnect()
            self._log_to_monitor('温箱串口已关闭', 'info')
            self.console_logger.info('温箱串口已关闭')
            self.window['-STATUS-'].update('串口状态: 已关闭')
        except Exception as e:
            self.console_logger.error(f'关闭串口失败: {e}')
            self._log_to_monitor(f'关闭串口失败: {e}', 'error')
            self.window['-STATUS-'].update(f'串口状态: 关闭失败')
    
    def _update_button_states(self):
        try:
            if self.is_testing:
                self.window['-LOAD_SCRIPT-'].update(disabled=True)
                self.window['-PREVIEW_SCRIPT-'].update(disabled=True)
                self.window['-VALIDATE_SCRIPT-'].update(disabled=True)
                self.window['-START_TEST-'].update(disabled=True)
            else:
                self.window['-LOAD_SCRIPT-'].update(disabled=False)
                self.window['-PREVIEW_SCRIPT-'].update(disabled=False)
                self.window['-VALIDATE_SCRIPT-'].update(disabled=False)
                self.window['-START_TEST-'].update(disabled=False)
        except Exception as e:
            self.console_logger.error(f'更新按钮状态失败: {e}')
    
    def _start_chamber(self):
        if not self.chamber_controller:
            if not self._init_chamber_controller():
                return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法启动温箱', 'error')
            return
        
        success = self.chamber_controller.start_chamber()
        if success:
            self._log_to_monitor('温箱启动成功', 'info')
        else:
            self._log_to_monitor('温箱启动失败', 'error')

    def _stop_chamber(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'warning')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法停止温箱', 'error')
            return
        
        success = self.chamber_controller.stop_chamber()
        if success:
            self._log_to_monitor('温箱停止成功', 'info')
        else:
            self._log_to_monitor('温箱停止失败', 'error')

    def _read_temperature(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'error')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法读取温度', 'error')
            return
        
        temperature = self.chamber_controller.read_temperature()
        if temperature is not None:
            self.window['-CHAMBER_TEMP-'].update(f'{temperature:.1f}°C')
            self._log_to_monitor(f'当前温箱温度: {temperature:.1f}°C', 'info')
        else:
            self._log_to_monitor('读取温度失败', 'error')

    def _set_temperature(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'warning')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法设定温度', 'error')
            return
        
        temp_input = self.window['-TEMP_INPUT-'].get()
        try:
            temperature = float(temp_input)
            
            if temperature < -60:
                self._log_to_monitor(f'温度过低，最低温度限制为-60°C', 'warning')
                return
            
            if temperature > 150:
                self._log_to_monitor(f'温度过高，最高温度限制为150°C', 'warning')
                return
            
            success = self.chamber_controller.set_temperature(temperature)
            if success:
                self._log_to_monitor(f'设定温度成功: {temperature}°C', 'info')
            else:
                self._log_to_monitor('设定温度失败', 'error')
        except ValueError:
            self._log_to_monitor('温度输入无效', 'error')

    def _load_script(self):
        script_path = self.window['-SCRIPT_PATH-'].get()
        parser = TestScriptParser(self.console_logger)
        
        commands = parser.parse_script(script_path)
        if commands:
            self.test_commands = commands
            self.window['-COMMAND_COUNT-'].update(str(len(commands)))
            self._log_to_monitor(f'测试脚本加载成功，共{len(commands)}条命令', 'info')
        else:
            self._log_to_monitor('测试脚本加载失败', 'error')

    def _validate_script(self):
        script_path = self.window['-SCRIPT_PATH-'].get()
        parser = TestScriptParser(self.console_logger)
        
        is_valid, errors = parser.validate_script(script_path)
        if is_valid:
            self._log_to_monitor('测试脚本验证通过', 'info')
        else:
            error_msg = '测试脚本验证失败:\n' + '\n'.join(errors)
            self._log_to_monitor(error_msg, 'error')
    
    def _preview_script(self):
        script_path = self.window['-SCRIPT_PATH-'].get()
        
        if not script_path or not os.path.exists(script_path):
            self._log_to_monitor('请先选择脚本文件', 'warning')
            return
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            layout = [
                [sg.Text('脚本预览', size=(20, 1), justification='center')],
                [sg.HSeparator()],
                [sg.Multiline(content, size=(60, 30), disabled=True, autoscroll=True)],
                [sg.HSeparator()],
                [sg.Button('关闭', key='-CLOSE_PREVIEW-', size=(10, 1))]
            ]
            
            preview_window = sg.Window('脚本预览', layout, modal=True, size=(700, 500))
            
            while True:
                event, values = preview_window.read()
                
                if event in (sg.WIN_CLOSED, '-CLOSE_PREVIEW-'):
                    break
            
            preview_window.close()
            
            self._log_to_monitor(f'预览脚本: {script_path}', 'info')
            
        except Exception as e:
            self.console_logger.error(f'预览脚本失败: {e}')
            self._log_to_monitor(f'预览脚本失败: {e}', 'error')
    
    def _select_script(self):
        try:
            script_path = sg.popup_get_file(
                '选择测试脚本文件',
                initial_folder='./',
                file_types=(('INI Files', '*.ini'),),
                no_titlebar=True
            )
            
            if script_path:
                self.window['-SCRIPT_PATH-'].update(script_path)
                self._log_to_monitor(f'已选择脚本: {script_path}', 'info')
            else:
                self._log_to_monitor('未选择脚本文件', 'warning')
        except Exception as e:
            self.console_logger.error(f'选择脚本失败: {e}')
            self._log_to_monitor(f'选择脚本失败: {e}', 'error')
    
    def _start_test(self):
        if not self.test_commands:
            self._log_to_monitor('请先加载测试脚本', 'warning')
            return
        
        if not self._init_test_executor():
            self._log_to_monitor('初始化测试执行器失败', 'error')
            return
        
        selected_hosts = []
        
        if self.window['-CHECK_HOST_1-'].get():
            selected_hosts.append('test_host_1')
        if self.window['-CHECK_HOST_2-'].get():
            selected_hosts.append('test_host_2')
        if self.window['-CHECK_HOST_3-'].get():
            selected_hosts.append('test_host_3')
        if self.window['-CHECK_HOST_4-'].get():
            selected_hosts.append('test_host_4')
        
        if not selected_hosts:
            self._log_to_monitor('请先选择要测试的主板', 'warning')
            return
        
        self.test_executor.set_selected_hosts(selected_hosts)
        self._log_to_monitor(f'已选择测试主板: {", ".join(selected_hosts)}', 'info')
        
        self.is_testing = True
        self._update_button_states()
        
        self.test_thread = self.thread_pool.submit(self._run_test)
        
        if not self.test_thread:
            self._log_to_monitor('创建测试线程失败', 'error')
            self.is_testing = False
            self._update_button_states()
            return

    def _run_test(self):
        try:
            self._update_host_info()
            self.real_time_monitor.start_monitoring()
            success = self.test_executor.execute_commands(self.test_commands)
            
            if success:
                self._log_to_monitor('测试完成', 'info')
                self._generate_report()
            else:
                self._log_to_monitor('测试失败', 'error')
        except Exception as e:
            self.console_logger.error(f'测试执行异常: {e}')
            self._log_to_monitor(f'测试执行异常: {e}', 'error')
        finally:
            self.real_time_monitor.stop_monitoring()
            self.is_testing = False
            self._update_button_states()

    def _pause_test(self):
        if self.test_executor:
            self.test_executor.pause_test()

    def _stop_test(self):
        if self.test_executor:
            self.test_executor.stop_test()

    def _generate_report(self):
        try:
            test_time = self.test_executor.test_time
            test_log_dir = self.config['logging']['test_log_dir']
            
            analysis_result = self.test_analyzer.analyze_test_result(test_time, test_log_dir)
            
            report_path = os.path.join(test_log_dir, test_time, 'report.html')
            success = self.html_generator.generate_report(analysis_result, report_path)
            
            if success:
                self.window['-REPORT_PATH-'].update(report_path)
                self._log_to_monitor(f'测试报告生成成功: {report_path}', 'info')
            else:
                self._log_to_monitor('测试报告生成失败', 'error')
        except Exception as e:
            self.console_logger.error(f'生成测试报告失败: {e}')
            self._log_to_monitor(f'生成测试报告失败: {e}', 'error')

    def _open_report(self):
        report_path = self.window['-REPORT_PATH-'].get()
        if report_path and os.path.exists(report_path):
            os.startfile(report_path)
        else:
            self._log_to_monitor('报告文件不存在', 'warning')
    
    def _wake_selected_hosts(self, selected_hosts: List[str]):
        try:
            if not self.host_manager:
                if not self._init_host_manager():
                    self._log_to_monitor('主机管理器初始化失败', 'error')
                    return
            
            self.host_manager.wake_selected_hosts(selected_hosts)
            self._log_to_monitor(f'已发送WOL唤醒命令到: {", ".join(selected_hosts)}', 'info')
            
        except Exception as e:
            self.console_logger.error(f'唤醒主板异常: {e}')
            self._log_to_monitor(f'唤醒主板异常: {e}', 'error')
    
    def _shutdown_selected_hosts(self, selected_hosts: List[str]):
        try:
            if not self.host_manager:
                if not self._init_host_manager():
                    self._log_to_monitor('主机管理器初始化失败', 'error')
                    return
            
            self.host_manager.shutdown_all_hosts(selected_hosts=selected_hosts)
            self._log_to_monitor(f'已发送关机命令到: {", ".join(selected_hosts)}', 'info')
            
        except Exception as e:
            self.console_logger.error(f'关机主板异常: {e}')
            self._log_to_monitor(f'关机主板异常: {e}', 'error')
    
    def _connect_selected_hosts(self, selected_hosts: List[str]):
        try:
            print(f"[DEBUG] _connect_selected_hosts 开始执行")
            print(f"[DEBUG] selected_hosts: {selected_hosts}")
            
            if not self.host_manager:
                print(f"[DEBUG] host_manager未初始化，开始初始化")
                self._log_to_monitor('主机管理器未初始化，正在初始化...', 'info')
                
                if not self._init_host_manager():
                    print(f"[DEBUG] host_manager初始化失败")
                    self._log_to_monitor('主机管理器初始化失败', 'error')
                    return
                
                print(f"[DEBUG] host_manager初始化成功")
                self._log_to_monitor('主机管理器初始化成功', 'info')
            
            print(f"[DEBUG] host_manager已初始化")
            print(f"[DEBUG] host_manager.hosts数量: {len(self.host_manager.hosts)}")
            for i, host in enumerate(self.host_manager.hosts, 1):
                print(f"[DEBUG] host[{i}]: name={host.name}, ip={host.ip}, ssh_client={host.ssh_client is not None}")
            
            self._log_to_monitor(f'开始连接主板: {", ".join(selected_hosts)}', 'info')
            print(f"[DEBUG] 开始调用 connect_selected_hosts")
            
            success = self.host_manager.connect_selected_hosts(selected_hosts)
            
            print(f"[DEBUG] connect_selected_hosts 返回值: {success}")
            
            if success:
                self._log_to_monitor('主板连接成功', 'info')
            else:
                self._log_to_monitor('主板连接失败，尝试获取SSD信息', 'warning')
            
            print(f"[DEBUG] 开始调用 get_selected_ssd_info")
            
            all_ssd_info = self.host_manager.get_selected_ssd_info(selected_hosts)
            
            print(f"[DEBUG] all_ssd_info: {all_ssd_info}")
            print(f"[DEBUG] all_ssd_info keys: {list(all_ssd_info.keys())}")
            print(f"[DEBUG] all_ssd_info 数量: {len(all_ssd_info)}")
            
            for i, host in enumerate(self.host_manager.hosts, 1):
                print(f"[DEBUG] 处理 host[{i}]: name={host.name}")
                
                if host.name in selected_hosts:
                    print(f"[DEBUG] host {host.name} 在 selected_hosts 中")
                    
                    info_text = f'主板: {host.name}\n'
                    
                    host_ssd_count = 0
                    for ssd_sn, ssd_info in all_ssd_info.items():
                        if ssd_info.get('host') == host.name and ssd_sn != 'unknown':
                            host_ssd_count += 1
                            print(f"[DEBUG] 找到SSD: {ssd_sn}, info: {ssd_info}")
                            
                            info_text += f'SSD SN: {ssd_sn}\n'
                            
                            ssd_path = ssd_info.get('path', '')
                            print(f"[DEBUG] ssd_path: {ssd_path}")
                            
                            try:
                                link_status = host.get_ssd_link_status(ssd_path)
                                print(f"[DEBUG] link_status: {link_status}")
                                link_info = link_status.get('link', 'N/A')
                                if link_info == 'N/A' or not link_info:
                                    link_info = '未知'
                                info_text += f'  链路状态: {link_info}\n'
                            except Exception as e:
                                print(f"[DEBUG] 获取链路状态异常: {e}")
                                info_text += f'  链路状态: 获取失败\n'
                            
                            smart_info = host.get_ssd_smart(ssd_path)
                            print(f"[DEBUG] smart_info: {smart_info}")
                            temp = host.get_ssd_temperature(ssd_path)
                            if temp is not None:
                                info_text += f'  温度: {temp}°C\n'
                            else:
                                info_text += f'  温度: N/A\n'
                            info_text += '-' * 30 + '\n'
                    
                    if host_ssd_count == 0:
                        info_text += f'{host.name} 未找到SSD信息\n'
                    
                    print(f"[DEBUG] info_text: {repr(info_text)}")
                    
                    gui_key = f'-SSD_INFO_{i}-'
                    print(f"[DEBUG] 更新GUI key: {gui_key}")
                    print(f"[DEBUG] 更新内容: {repr(info_text)}")
                    self.window[gui_key].update(info_text)
                    self.window.refresh()
                    print(f"[DEBUG] GUI更新完成")
                else:
                    print(f"[DEBUG] host {host.name} 不在 selected_hosts 中")
                    gui_key = f'-SSD_INFO_{i}-'
                    self.window[gui_key].update(f'{host.name} 未连接')
        except Exception as e:
            print(f"[DEBUG] 异常: {e}")
            print(f"[DEBUG] 异常类型: {type(e).__name__}")
            import traceback
            print(f"[DEBUG] 异常堆栈:\n{traceback.format_exc()}")
            self.console_logger.error(f'连接主板异常: {e}')
            self._log_to_monitor(f'连接主板异常: {e}', 'error')
    
    def _start_monitor(self):
        self.is_monitoring = True
        self.monitor_thread = self.thread_pool.submit(self._monitor_loop)

    def _monitor_loop(self):
        while self.is_monitoring:
            try:
                if self.host_manager:
                    self._update_host_info()
                
                time.sleep(5)
            except Exception as e:
                self.console_logger.error(f'监控循环异常: {e}')
                time.sleep(5)

    def run(self):
        self._start_monitor()
        
        while True:
            event, values = self.window.read(timeout=100)
            
            if event == sg.WIN_CLOSED:
                self.is_monitoring = False
                break
            
            elif event == '-START_CHAMBER-':
                self._start_chamber()
            
            elif event == '-STOP_CHAMBER-':
                self._stop_chamber()
            
            elif event == '-READ_TEMP-':
                self._read_temperature()
            
            elif event == '-SET_TEMP-':
                self._set_temperature()
            
            elif event == '-CHAMBER_DEBUG-':
                self._update_chamber_debug()
            
            elif event == '-CONNECT_SERIAL-':
                self._connect_serial()
            
            elif event == '-CLOSE_SERIAL-':
                self._close_serial()
            
            elif event == '-SAVE_COM-':
                self._save_com_port()
            
            elif event == '-WAKE_HOSTS-':
                selected_hosts = []
                
                if values['-CHECK_HOST_1-']:
                    selected_hosts.append('test_host_1')
                if values['-CHECK_HOST_2-']:
                    selected_hosts.append('test_host_2')
                if values['-CHECK_HOST_3-']:
                    selected_hosts.append('test_host_3')
                if values['-CHECK_HOST_4-']:
                    selected_hosts.append('test_host_4')
                
                if selected_hosts:
                    self._log_to_monitor(f'已选择主板: {", ".join(selected_hosts)}, 准备唤醒...', 'info')
                    
                    confirm = sg.popup_ok_cancel(
                        '确认唤醒',
                        f'将唤醒以下主板:\n{",\n".join(selected_hosts)}\n\n是否继续?',
                        button_color=('black', 'purple'),
                        auto_close=False
                    )
                    
                    if confirm == 'OK':
                        self._wake_selected_hosts(selected_hosts)
                        self._log_to_monitor(f'唤醒操作完成', 'info')
                    else:
                        self._log_to_monitor('唤醒操作已取消', 'warning')
                else:
                    self._log_to_monitor('未选择主板', 'warning')
            
            elif event == '-SHUTDOWN_HOSTS-':
                selected_hosts = []
                
                if values['-CHECK_HOST_1-']:
                    selected_hosts.append('test_host_1')
                if values['-CHECK_HOST_2-']:
                    selected_hosts.append('test_host_2')
                if values['-CHECK_HOST_3-']:
                    selected_hosts.append('test_host_3')
                if values['-CHECK_HOST_4-']:
                    selected_hosts.append('test_host_4')
                
                if selected_hosts:
                    self._log_to_monitor(f'已选择主板: {", ".join(selected_hosts)}, 准备关机...', 'info')
                    
                    confirm = sg.popup_ok_cancel(
                        '确认关机',
                        f'将关闭以下主板:\n{",\n".join(selected_hosts)}\n\n是否继续?',
                        button_color=('black', 'darkred'),
                        auto_close=False
                    )
                    
                    if confirm == 'OK':
                        self._shutdown_selected_hosts(selected_hosts)
                        self._log_to_monitor(f'关机操作完成', 'info')
                    else:
                        self._log_to_monitor('关机操作已取消', 'warning')
                else:
                    self._log_to_monitor('未选择主板', 'warning')
            
            elif event == '-CONNECT_HOSTS-':
                selected_hosts = []
                
                if values['-CHECK_HOST_1-']:
                    selected_hosts.append('test_host_1')
                if values['-CHECK_HOST_2-']:
                    selected_hosts.append('test_host_2')
                if values['-CHECK_HOST_3-']:
                    selected_hosts.append('test_host_3')
                if values['-CHECK_HOST_4-']:
                    selected_hosts.append('test_host_4')
                
                if selected_hosts:
                    self._log_to_monitor(f'已选择主板: {", ".join(selected_hosts)}, 准备连接...', 'info')
                    
                    confirm = sg.popup_ok_cancel(
                        '确认连接',
                        f'将连接以下主板:\n{",\n".join(selected_hosts)}\n\n是否继续?',
                        button_color=('black', 'blue'),
                        auto_close=False
                    )
                    
                    if confirm == 'OK':
                        self._connect_selected_hosts(selected_hosts)
                        self._log_to_monitor(f'连接操作完成', 'info')
                    else:
                        self._log_to_monitor('连接操作已取消', 'warning')
                else:
                    self._log_to_monitor('未选择主板', 'warning')
                
                if self.test_executor:
                    self.test_executor.set_selected_hosts(selected_hosts)
            
            elif event == '-SELECT_SCRIPT-':
                self._select_script()
            
            elif event == '-LOAD_SCRIPT-':
                self._load_script()
            
            elif event == '-PREVIEW_SCRIPT-':
                self._preview_script()
            
            elif event == '-VALIDATE_SCRIPT-':
                self._validate_script()
            
            elif event == '-START_TEST-':
                self._start_test()
            
            elif event == '-PAUSE_TEST-':
                self._pause_test()
            
            elif event == '-STOP_TEST-':
                self._stop_test()
            
            elif event == '-GENERATE_REPORT-':
                self._generate_report()
            
            elif event == '-OPEN_REPORT-':
                self._open_report()
        
        self.window.close()
        self.console_logger.info('NVMe SSD测试系统关闭')


def check_single_instance():
    import win32event
    import winerror
    import win32api
    import sys
    
    mutex_name = 'NVMeTestSystem_SingleInstance_Mutex'
    
    try:
        mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            sg.popup_error('NVMe SSD测试系统已在运行中！\n请先关闭已运行的实例。', title='错误')
            sys.exit(1)
        return mutex
    except Exception as e:
        print(f'单实例检查失败: {e}')
        return None


if __name__ == '__main__':
    import os
    import win32api
    
    single_instance_mutex = check_single_instance()
    
    app = NVMeTestGUI()
    app.run()
    
    if single_instance_mutex:
        win32api.CloseHandle(single_instance_mutex)
