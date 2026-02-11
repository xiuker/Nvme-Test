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
        
        # 测试报告路径设置
        self.user_report_path = None
        
        self._setup_signal_handlers()
        self._setup_exit_handlers()
        
        self.window = self._create_window()
        self.window.maximize()
        
        serial_config = self.config['serial']
        self.window['-CURRENT_COM-'].update(serial_config['port'])
        self.window['-STATUS-'].update('串口状态: 已关闭')
        
        # 初始化主机管理器，获取并显示MAC/IP地址
        self._init_host_manager()
        self._update_host_info()
        
        self.console_logger.info('NVMe SSD测试系统启动')
        
        # 读取默认报告路径并显示
        default_report_path = self.config['logging']['test_log_dir']
        # 转换为绝对路径
        default_report_path = os.path.abspath(default_report_path)
        
        # 确保默认报告目录存在
        if not os.path.exists(default_report_path):
            try:
                os.makedirs(default_report_path, exist_ok=True)
                self.console_logger.info(f'已创建默认报告目录: {default_report_path}')
            except Exception as e:
                self.console_logger.error(f'创建默认报告目录失败: {e}')
        
        self.window['-REPORT_PATH-'].update(default_report_path)
        
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
        
        # 收到信号时关闭线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True, timeout=5)
            self.console_logger.info('线程池已关闭')
        
        sys.exit(0)

    def _cleanup_on_exit(self):
        self.console_logger.info('程序退出，执行清理...')
        self._cleanup()
        
        # 程序退出时关闭线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True, timeout=5)
            self.console_logger.info('线程池已关闭')

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
        chamber_controls_frame = [
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
        
        chamber_log_frame = [
            [sg.Multiline('', key='-CHAMBER_LOG-', size=(80, 80), disabled=True, autoscroll=True)]
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
            [sg.Text('当前温度:', size=(12, 1)), 
             sg.Text('0.0°C', key='-CURRENT_TEMP-', size=(10, 1), text_color='dark blue')],
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
            [sg.Button('选择存储路径', key='-SELECT_REPORT_PATH-', size=(15, 1)),
             sg.Button('打开路径', key='-OPEN_REPORT_DIR-', size=(15, 1))],
            [sg.Text('测试报告路径:', size=(10, 1)), 
             sg.Input(key='-REPORT_PATH-', size=(30, 1), readonly=True)]
        ]

        left_column = [
            [sg.Frame('测试脚本', test_script_frame, size=(300, 150))],
            [sg.Frame('测试控制', test_control_frame, size=(300, 300))],
            [sg.Frame('测试报告', report_frame, size=(300, 150))]
        ]
        # 重新设计：一大张表格形式，横向标题为IP/MAC，SSD1，SSD2，SSD3，SSD4，纵向标题为主板1-4
        
        # 表格列定义
        table_columns = ['主板名称', 'IP/MAC地址', 'SSD 1', 'SSD 2', 'SSD 3', 'SSD 4']
        
        # 初始表格数据
        table_data = [
            ['test_host_1', '', '', '', '', ''],
            ['test_host_2', '', '', '', '', ''],
            ['test_host_3', '', '', '', '', ''],
            ['test_host_4', '', '', '', '', '']
        ]
        
        # 创建大表格
        test_control_table = sg.Table(
            values=table_data,
            headings=table_columns,
            key='-TEST_CONTROL_TABLE-',
            auto_size_columns=False,
            col_widths=[15, 25, 30, 30, 30, 30],
            justification='left',
            size=(None, 15),
            enable_events=False,
            vertical_scroll_only=False,
            border_width=1,  # 添加边框
            row_height=120,    # 增加行高（纵向间距）
            alternating_row_color='#f0f0f0',  # 添加交替行颜色，增强可读性
            background_color='white',  # 背景色
            text_color='black',  # 文字颜色
            header_background_color='#e0e0e0',  # 表头背景色
            header_text_color='black',  # 表头文字颜色
            header_font=('Arial', 10, 'bold')  # 表头字体
        )
        
        # 测试控制内容：只包含一个大表格
        test_control_content = [
            [test_control_table]
        ]

        right_column = [
            [sg.Column(test_control_content)]
            # , scrollable=True, vertical_scroll_only=True, size=(None, 700))]
        ]

        test_control_tab = [
            [sg.Column(left_column, element_justification='c'),
             sg.VSeparator(),
             sg.Column(right_column, element_justification='c')]
        ]

        chamber_tab = [
            [sg.Frame('温箱串口操作', chamber_controls_frame, size=(350, 350)),
            sg.Frame('温箱操作记录', chamber_log_frame, size=(350, 350))]
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
    
    def _log_chamber_operation(self, message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f'[{timestamp}] {message}\n'
        
        self.window['-CHAMBER_LOG-'].print(log_message, end='')

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
                        self._log_to_monitor('温箱控制器初始化失败，但将继续执行测试（不包含温度控制）', 'warning')
                        self.chamber_controller = None
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
        # 更新全局进度信息
        self.window['-CURRENT_TEMP-'].update(f'{progress.current_temperature:.1f}°C')
        self.window['-CYCLE_PROGRESS-'].update(f'{progress.current_cycle}/{progress.total_cycles}')
        self.window['-HOLD_TIME-'].update(f'{progress.hold_time}秒')
        
        # 更新SSD信息到GUI
        if hasattr(progress, 'ssd_status') and progress.ssd_status:
            self._update_ssd_info(ssd_info=progress.ssd_status)
        
        # 更新主机进度信息到表格
        if hasattr(progress, 'host_progress') and progress.host_progress:
            self._update_host_info_with_progress(progress.host_progress)
        
        if progress.is_running:
            self.window['-STATUS-'].update('测试运行中...')
        elif progress.is_paused:
            self.window['-STATUS-'].update('测试已暂停')
        else:
            self.window['-STATUS-'].update('测试停止')
    
    def _update_host_info_with_progress(self, host_progress: Dict):
        """更新主机信息，包含测试进度"""
        if not self.host_manager:
            return
        
        try:
            # 创建新的表格数据
            new_data = []
            for host in self.host_manager.hosts:
                # 构建IP/MAC地址文本
                ip_mac_text = f'IP: {host.ip}\nMAC: {host.mac}'
                
                # 构建主板名称，包含测试进度
                host_name = host.name
                if host.name in host_progress:
                    progress = host_progress[host.name]
                    current_command = progress.get('current_command_index', 0)
                    total_commands = self.test_executor.progress.total_commands if hasattr(self, 'test_executor') else 0
                    current_test_item = progress.get('current_test_item', '')
                    current_cycle = progress.get('current_cycle', 0)
                    total_cycles = progress.get('total_cycles', 0)
                    
                    # 构建进度信息
                    progress_info = f'({current_command}/{total_commands} - {current_test_item}'
                    # 只有 PCT 测试需要显示轮次信息
                    if total_cycles > 0 and current_test_item == 'PCT':
                        progress_info += f' - {current_cycle}/{total_cycles}'
                    progress_info += ')'
                    
                    # 添加开始时间信息
                    start_time = progress.get('start_time', '')
                    if start_time:
                        progress_info += f'\n开始时间: {start_time}'
                    
                    # 主板名称与进度信息换行显示
                    host_name_with_progress = f'{host_name}\n{progress_info}'
                else:
                    host_name_with_progress = host_name
                
                # 添加到新的表格数据中
                new_data.append([host_name_with_progress, ip_mac_text, '', '', '', ''])
            
            # 更新表格
            self.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
            self.window.refresh()
                
        except Exception as e:
            pass

    def _update_ssd_info(self, silent: bool = False, ssd_info: Optional[Dict] = None):
        if not self.host_manager:
            return
        
        try:
            # 如果提供了SSD信息，就使用它；否则从host_manager获取
            if ssd_info:
                all_ssd_info = ssd_info
            else:
                all_ssd_info = self.host_manager.get_all_ssd_info(silent=silent)
            
            # 获取当前表格数据
            current_table_data = self.window['-TEST_CONTROL_TABLE-'].get()
            
            # 初始化新的表格数据
            new_table_data = []
            
            # 初始化SSD信息
            host_ssd_info = {}
            for host in self.host_manager.hosts:
                host_ssd_info[host.name] = ['', '', '', '']  # 每个主板4个SSD槽位
            
            # 处理SSD信息
            for ssd_sn, ssd_info in all_ssd_info.items():
                if ssd_sn == 'unknown':
                    continue
                
                host_name = ssd_info.get('host')
                if not host_name:
                    continue
                
                # 简单分配SSD到对应的SSD槽位（实际应用中可能需要更复杂的映射）
                ssd_slot = 0
                while ssd_slot < 4 and host_ssd_info[host_name][ssd_slot]:
                    ssd_slot += 1
                
                if ssd_slot < 4:
                    # 构建SSD信息文本
                    ssd_info_text = f'SN: {ssd_sn}\n'
                    ssd_info_text += f'路径: {ssd_info.get("path", "N/A")}\n'
                    host_ssd_info[host_name][ssd_slot] = ssd_info_text
            
            # 处理每个主机的信息
            for i, host in enumerate(self.host_manager.hosts):
                # 保留当前的主板名称（可能包含进度信息）
                host_name_with_progress = current_table_data[i][0] if i < len(current_table_data) else host.name
                
                # 获取IP/MAC地址
                ip_mac_text = f'IP: {host.ip}\nMAC: {host.mac}'
                
                # 获取SSD信息
                ssd_infos = host_ssd_info.get(host.name, ['', '', '', ''])
                
                # 构建新的行数据
                new_row = [host_name_with_progress, ip_mac_text] + ssd_infos
                new_table_data.append(new_row)
            
            # 更新表格
            self.window['-TEST_CONTROL_TABLE-'].update(values=new_table_data)
            self.window.refresh()
                
        except Exception as e:
            if not silent:
                self.console_logger.error(f'更新SSD信息失败: {e}')
    
    def _update_host_info(self):
        if not self.host_manager:
            return
        
        try:
            # 获取当前表格数据
            current_table_data = self.window['-TEST_CONTROL_TABLE-'].get()
            
            # 创建新的表格数据
            new_data = []
            for i, host in enumerate(self.host_manager.hosts):
                # 构建IP/MAC地址文本
                ip_mac_text = f'IP: {host.ip}\nMAC: {host.mac}'
                
                # 保留当前的主板名称（可能包含进度信息）
                host_name_with_progress = current_table_data[i][0] if i < len(current_table_data) else host.name
                
                # 添加到新的表格数据中
                new_data.append([host_name_with_progress, ip_mac_text, '', '', '', ''])
            
            # 更新表格
            self.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
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
                self._log_chamber_operation('串口已处于连接状态')
                return
            
            self._log_chamber_operation(f'正在连接串口: {self.chamber_controller.port}')
            self.chamber_controller._connect()
            if self.chamber_controller.serial_conn:
                self._log_to_monitor(f'温箱串口已连接: {self.chamber_controller.port}', 'info')
                self._log_chamber_operation(f'温箱串口已连接: {self.chamber_controller.port}')
                self.console_logger.info(f'温箱串口已连接: {self.chamber_controller.port}')
                self.window['-STATUS-'].update(f'串口状态: 已连接({self.chamber_controller.port})')
            else:
                self._log_to_monitor('串口连接失败', 'error')
                self._log_chamber_operation('串口连接失败')
                self.console_logger.error('串口连接失败')
                self.window['-STATUS-'].update(f'串口状态: 连接失败')
        except Exception as e:
            self.console_logger.error(f'连接串口失败: {e}')
            self._log_to_monitor(f'连接串口失败: {e}', 'error')
            self._log_chamber_operation(f'连接串口失败: {e}')
            self.window['-STATUS-'].update(f'串口状态: 连接失败')
    
    def _close_serial(self):
        try:
            if not self.chamber_controller:
                self._log_to_monitor('温箱控制器未初始化', 'warning')
                self._log_chamber_operation('温箱控制器未初始化')
                return
            
            if not self.chamber_controller.serial_conn:
                self._log_to_monitor('串口已处于关闭状态', 'warning')
                self._log_chamber_operation('串口已处于关闭状态')
                return
            
            self._log_chamber_operation('正在关闭串口')
            self.chamber_controller._disconnect()
            self._log_to_monitor('温箱串口已关闭', 'info')
            self._log_chamber_operation('温箱串口已关闭')
            self.console_logger.info('温箱串口已关闭')
            self.window['-STATUS-'].update('串口状态: 已关闭')
        except Exception as e:
            self.console_logger.error(f'关闭串口失败: {e}')
            self._log_to_monitor(f'关闭串口失败: {e}', 'error')
            self._log_chamber_operation(f'关闭串口失败: {e}')
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
            self._log_chamber_operation('串口未连接，无法启动温箱')
            return
        
        self._log_chamber_operation('正在启动温箱')
        success = self.chamber_controller.start_chamber()
        if success:
            self._log_to_monitor('温箱启动成功', 'info')
            self._log_chamber_operation('温箱启动成功')
        else:
            self._log_to_monitor('温箱启动失败', 'error')
            self._log_chamber_operation('温箱启动失败')

    def _stop_chamber(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'warning')
            self._log_chamber_operation('温箱控制器未初始化')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法停止温箱', 'error')
            self._log_chamber_operation('串口未连接，无法停止温箱')
            return
        
        self._log_chamber_operation('正在停止温箱')
        success = self.chamber_controller.stop_chamber()
        if success:
            self._log_to_monitor('温箱停止成功', 'info')
            self._log_chamber_operation('温箱停止成功')
        else:
            self._log_to_monitor('温箱停止失败', 'error')
            self._log_chamber_operation('温箱停止失败')

    def _read_temperature(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'error')
            self._log_chamber_operation('温箱控制器未初始化')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法读取温度', 'error')
            self._log_chamber_operation('串口未连接，无法读取温度')
            return
        
        self._log_chamber_operation('正在读取温箱温度')
        temperature = self.chamber_controller.read_temperature()
        if temperature is not None:
            self.window['-CHAMBER_TEMP-'].update(f'{temperature:.1f}°C')
            self._log_to_monitor(f'当前温箱温度: {temperature:.1f}°C', 'info')
            self._log_chamber_operation(f'当前温箱温度: {temperature:.1f}°C')
        else:
            self._log_to_monitor('读取温度失败', 'error')
            self._log_chamber_operation('读取温度失败')

    def _set_temperature(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'warning')
            self._log_chamber_operation('温箱控制器未初始化')
            return
        
        if not self.chamber_controller.serial_conn:
            self._log_to_monitor('串口未连接，无法设定温度', 'error')
            self._log_chamber_operation('串口未连接，无法设定温度')
            return
        
        temp_input = self.window['-TEMP_INPUT-'].get()
        try:
            temperature = float(temp_input)
            
            if temperature < -60:
                self._log_to_monitor(f'温度过低，最低温度限制为-60°C', 'warning')
                self._log_chamber_operation(f'温度过低，最低温度限制为-60°C')
                return
            
            if temperature > 150:
                self._log_to_monitor(f'温度过高，最高温度限制为150°C', 'warning')
                self._log_chamber_operation(f'温度过高，最高温度限制为150°C')
                return
            
            self._log_chamber_operation(f'正在设定温箱温度: {temperature}°C')
            success = self.chamber_controller.set_temperature(temperature)
            if success:
                self._log_to_monitor(f'设定温度成功: {temperature}°C', 'info')
                self._log_chamber_operation(f'设定温度成功: {temperature}°C')
            else:
                self._log_to_monitor('设定温度失败', 'error')
                self._log_chamber_operation('设定温度失败')
        except ValueError:
            self._log_to_monitor('温度输入无效', 'error')
            self._log_chamber_operation('温度输入无效')

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
            # 验证通过后，解析脚本获取命令条数
            commands = parser.parse_script(script_path)
            if commands:
                self.test_commands = commands
                self.window['-COMMAND_COUNT-'].update(str(len(commands)))
                self._log_to_monitor(f'测试脚本验证通过，共{len(commands)}条命令', 'info')
            else:
                self._log_to_monitor('测试脚本验证通过但解析失败', 'warning')
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
            # 转换为绝对路径
            test_log_dir = os.path.abspath(test_log_dir)
            
            analysis_result = self.test_analyzer.analyze_test_result(test_time, test_log_dir)
            
            # 使用用户选择的存储路径或默认路径
            if self.user_report_path:
                report_path = os.path.join(self.user_report_path, f'report_{test_time}.html')
            else:
                report_path = os.path.join(test_log_dir, test_time, 'report.html')
            
            # 转换为绝对路径
            report_path = os.path.abspath(report_path)
            
            # 确保报告目录存在
            report_dir = os.path.dirname(report_path)
            os.makedirs(report_dir, exist_ok=True)
            
            success = self.html_generator.generate_report(analysis_result, report_path)
            
            if success:
                self.window['-REPORT_PATH-'].update(report_path)
                self._log_to_monitor(f'测试报告生成成功: {report_path}', 'info')
            else:
                self._log_to_monitor('测试报告生成失败', 'error')
        except Exception as e:
            self.console_logger.error(f'生成测试报告失败: {e}')
            self._log_to_monitor(f'生成测试报告失败: {e}', 'error')
    
    def _select_report_path(self):
        try:
            # 使用绝对路径作为初始文件夹
            initial_folder = self.user_report_path if self.user_report_path else os.path.abspath('./')
            
            folder_path = sg.popup_get_folder(
                '选择测试报告存储路径',
                initial_folder=initial_folder,
                no_titlebar=True
            )
            
            if folder_path:
                # 转换为绝对路径
                folder_path = os.path.abspath(folder_path)
                self.user_report_path = folder_path
                # 更新输入框显示当前选择的路径
                self.window['-REPORT_PATH-'].update(folder_path)
                self._log_to_monitor(f'已选择报告存储路径: {folder_path}', 'info')
            else:
                self._log_to_monitor('未选择报告存储路径', 'warning')
        except Exception as e:
            self.console_logger.error(f'选择报告存储路径失败: {e}')
            self._log_to_monitor(f'选择报告存储路径失败: {e}', 'error')
    
    def _open_report_dir(self):
        report_path = self.window['-REPORT_PATH-'].get()
        if not report_path:
            self._log_to_monitor('报告路径未设置', 'warning')
            return
        
        # 确保路径存在
        if not os.path.exists(report_path):
            # 尝试创建目录
            try:
                os.makedirs(report_path, exist_ok=True)
                self._log_to_monitor(f'已创建目录: {report_path}', 'info')
                os.startfile(report_path)
            except Exception as e:
                self._log_to_monitor(f'打开路径失败: {e}', 'error')
            return
        
        # 路径存在，区分文件和目录
        if os.path.isfile(report_path):
            # 如果是文件路径，打开其所在目录
            report_dir = os.path.dirname(report_path)
            os.startfile(report_dir)
            self._log_to_monitor(f'已打开文件所在目录: {report_dir}', 'info')
        else:
            # 如果是目录路径，直接打开目录
            os.startfile(report_path)
            self._log_to_monitor(f'已打开目录: {report_path}', 'info')

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
            
            # 只构建一次完整的表格数据
            table_data = []
            for host_item in self.host_manager.hosts:
                ip_mac_text = f'IP: {host_item.ip}\nMAC: {host_item.mac}'
                table_data.append([host_item.name, ip_mac_text, '', '', '', ''])
            
            # 遍历所有主机，更新对应的数据
            for i, host in enumerate(self.host_manager.hosts, 1):
                print(f"[DEBUG] 处理 host[{i}]: name={host.name}")
                
                # 查找当前主板在表格中的索引
                host_index = None
                for idx, row in enumerate(table_data):
                    if row[0] == host.name:
                        host_index = idx
                        break
                
                if host_index is not None:
                    if host.name in selected_hosts:
                        print(f"[DEBUG] host {host.name} 在 selected_hosts 中")
                        
                        # 初始化SSD信息
                        ssd_info_list = ['', '', '', '']
                        
                        host_ssd_count = 0
                        for ssd_sn, ssd_info in all_ssd_info.items():
                            if ssd_info.get('host') == host.name and ssd_sn != 'unknown':
                                host_ssd_count += 1
                                print(f"[DEBUG] 找到SSD: {ssd_sn}, info: {ssd_info}")
                                
                                ssd_path = ssd_info.get('path', '')
                                print(f"[DEBUG] ssd_path: {ssd_path}")
                                
                                # 构建SSD信息文本
                                ssd_info_text = f'SN: {ssd_sn}\n'
                                ssd_info_text += f'路径: {ssd_path}\n'
                                
                                # 获取链路状态
                                try:
                                    link_status = host.get_ssd_link_status(ssd_path)
                                    print(f"[DEBUG] link_status: {link_status}")
                                    link_info = link_status.get('link', 'N/A')
                                    if link_info == 'N/A' or not link_info:
                                        link_info = '未知'
                                    ssd_info_text += f'链路状态: {link_info}\n'
                                except Exception as e:
                                    print(f"[DEBUG] 获取链路状态异常: {e}")
                                    ssd_info_text += f'链路状态: 获取失败\n'
                                
                                # 获取温度信息
                                temp = host.get_ssd_temperature(ssd_path)
                                if temp is not None:
                                    ssd_info_text += f'温度: {temp}°C\n'
                                else:
                                    ssd_info_text += f'温度: N/A\n'
                                
                                # 将SSD数据分配到对应的槽位
                                ssd_slot = host_ssd_count - 1
                                if ssd_slot < 4:
                                    ssd_info_list[ssd_slot] = ssd_info_text
                        
                        # 更新SSD 1-4列
                        for j in range(4):
                            table_data[host_index][j+2] = ssd_info_list[j]
                    else:
                        print(f"[DEBUG] host {host.name} 不在 selected_hosts 中")
                        # 更新该主板的所有SSD槽位为未连接状态
                        for j in range(4):
                            table_data[host_index][j+2] = f'{host.name} 未连接\n'
            
            # 一次性更新表格，避免多次覆盖
            self.window['-TEST_CONTROL_TABLE-'].update(values=table_data)
            self.window.refresh()
            print(f"[DEBUG] GUI更新完成")
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
        # 保存上次的主机信息，用于检测变化
        last_host_info = []
        
        while self.is_monitoring:
            try:
                if self.host_manager:
                    # 构建当前主机信息
                    current_host_info = []
                    for host in self.host_manager.hosts:
                        ip_mac_text = f'IP: {host.ip}\nMAC: {host.mac}'
                        current_host_info.append([host.name, ip_mac_text])
                    
                    # 只有当主机信息发生变化时才更新表格
                    if current_host_info != last_host_info:
                        self._update_host_info()
                        last_host_info = current_host_info.copy()
                
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
            
            elif event == '-SELECT_REPORT_PATH-':
                self._select_report_path()
            
            elif event == '-OPEN_REPORT_DIR-':
                self._open_report_dir()
        
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
