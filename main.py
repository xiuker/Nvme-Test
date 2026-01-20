import os
import PySimpleGUI as sg
import threading
import time
import atexit
import signal
import sys
from typing import Optional, Dict
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
        sg.theme('DarkBlue3')
        
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
        
        self.thread_pool = ThreadPoolManager(max_workers=20, logger=self.console_logger)
        self.resource_cleaner = ResourceCleaner()
        self.resource_cleaner.set_logger(self.console_logger)
        self.memory_monitor = MemoryMonitor(logger=self.console_logger)
        
        self._setup_signal_handlers()
        self._setup_exit_handlers()
        
        self.window = self._create_window()
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
            [sg.Text('温箱温度:', size=(12, 1)), sg.Text('0.0°C', key='-CHAMBER_TEMP-', size=(10, 1), text_color='yellow')],
            [sg.Text('保温倒计时:', size=(12, 1)), sg.Text('0秒', key='-HOLD_TIME-', size=(10, 1), text_color='yellow')],
            [sg.HSeparator()],
            [sg.Button('启动温箱', key='-START_CHAMBER-', size=(12, 1)), 
             sg.Button('停止温箱', key='-STOP_CHAMBER-', size=(12, 1))],
            [sg.Button('读取温度', key='-READ_TEMP-', size=(12, 1)),
             sg.Button('设定温度', key='-SET_TEMP-', size=(12, 1))],
            [sg.Input(key='-TEMP_INPUT-', size=(10, 1)), sg.Text('°C')]
        ]

        test_script_frame = [
            [sg.Text('测试脚本:', size=(10, 1)), 
             sg.Input('./test_script.ini', key='-SCRIPT_PATH-', size=(30, 1)),
             sg.FileBrowse(file_types=(('INI Files', '*.ini'),))],
            [sg.Button('加载脚本', key='-LOAD_SCRIPT-', size=(10, 1)),
             sg.Button('验证脚本', key='-VALIDATE_SCRIPT-', size=(10, 1))],
            [sg.Text('脚本命令数:', size=(12, 1)), 
             sg.Text('0', key='-COMMAND_COUNT-', size=(5, 1), text_color='yellow')]
        ]

        test_control_frame = [
            [sg.Button('开始测试', key='-START_TEST-', size=(12, 1), button_color=('white', 'green')),
             sg.Button('暂停测试', key='-PAUSE_TEST-', size=(12, 1), button_color=('white', 'orange')),
             sg.Button('停止测试', key='-STOP_TEST-', size=(12, 1), button_color=('white', 'red'))],
            [sg.HSeparator()],
            [sg.Text('当前命令:', size=(12, 1)), 
             sg.Text('0/0', key='-COMMAND_PROGRESS-', size=(10, 1), text_color='yellow')],
            [sg.Text('当前测试项:', size=(12, 1)), 
             sg.Text('无', key='-CURRENT_TEST_ITEM-', size=(15, 1), text_color='yellow')],
            [sg.Text('当前温度:', size=(12, 1)), 
             sg.Text('0.0°C', key='-CURRENT_TEMP-', size=(10, 1), text_color='yellow')],
            [sg.Text('测试轮次:', size=(12, 1)), 
             sg.Text('0/0', key='-CYCLE_PROGRESS-', size=(10, 1), text_color='yellow')]
        ]

        ssd_info_frame = [
            [sg.Text('SSD信息监控', size=(20, 1), justification='center')],
            [sg.HSeparator()],
            [sg.Multiline('', key='-SSD_INFO-', size=(40, 10), disabled=True, autoscroll=True)]
        ]

        monitor_frame = [
            [sg.Text('实时监控日志', size=(20, 1), justification='center')],
            [sg.HSeparator()],
            [sg.Multiline('', key='-MONITOR_LOG-', size=(50, 15), disabled=True, autoscroll=True)]
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
            [sg.Frame('温箱控制', chamber_frame, size=(300, 250))],
            [sg.Frame('测试脚本', test_script_frame, size=(300, 120))],
            [sg.Frame('测试控制', test_control_frame, size=(300, 180))]
        ]

        middle_column = [
            [sg.Frame('SSD信息', ssd_info_frame, size=(350, 350))],
            [sg.Frame('测试报告', report_frame, size=(350, 150))]
        ]

        right_column = [
            [sg.Frame('实时监控', monitor_frame, size=(400, 500))]
        ]

        layout = [
            [sg.Text('NVMe SSD测试系统', size=(50, 1), justification='center', 
                    font=('Arial', 20, 'bold'), text_color='white')],
            [sg.HSeparator()],
            [sg.Column(left_column, element_justification='c'),
             sg.VSeparator(),
             sg.Column(middle_column, element_justification='c'),
             sg.VSeparator(),
             sg.Column(right_column, element_justification='c')],
            [sg.StatusBar('就绪', key='-STATUS-', size=(80, 1))]
        ]

        return sg.Window('NVMe SSD测试系统', layout, finalize=True, resizable=True)

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
            
            self.chamber_controller = ChamberController(
                port=serial_config['port'],
                baudrate=serial_config['baudrate'],
                bytesize=serial_config['bytesize'],
                parity=serial_config['parity'],
                stopbits=serial_config['stopbits'],
                timeout=serial_config['timeout'],
                command_set=chamber_config['command_set'],
                logger=self.console_logger
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
            if not self.chamber_controller:
                if not self._init_chamber_controller():
                    return False
            
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

    def _update_ssd_info(self):
        if not self.host_manager:
            return
        
        try:
            all_ssd_info = self.host_manager.get_all_ssd_info()
            info_text = ''
            
            for ssd_sn, info in all_ssd_info.items():
                info_text += f'SSD SN: {ssd_sn}\n'
                info_text += f'  MN: {info.get("MN", "N/A")}\n'
                info_text += f'  VID: {info.get("VID", "N/A")}\n'
                info_text += f'  DID: {info.get("DID", "N/A")}\n'
                info_text += f'  主机: {info.get("host", "N/A")}\n'
                info_text += f'  路径: {info.get("path", "N/A")}\n'
                info_text += '-'*30 + '\n'
            
            self.window['-SSD_INFO-'].update(info_text)
        except Exception as e:
            self.console_logger.error(f'更新SSD信息失败: {e}')

    def _start_chamber(self):
        if not self.chamber_controller:
            if not self._init_chamber_controller():
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
        
        success = self.chamber_controller.stop_chamber()
        if success:
            self._log_to_monitor('温箱停止成功', 'info')
        else:
            self._log_to_monitor('温箱停止失败', 'error')

    def _read_temperature(self):
        if not self.chamber_controller:
            self._log_to_monitor('温箱控制器未初始化', 'warning')
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
        
        temp_input = self.window['-TEMP_INPUT-'].get()
        try:
            temperature = float(temp_input)
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

    def _start_test(self):
        if not self.test_commands:
            self._log_to_monitor('请先加载测试脚本', 'warning')
            return
        
        if not self._init_test_executor():
            self._log_to_monitor('初始化测试执行器失败', 'error')
            return
        
        self.test_thread = self.thread_pool.submit(self._run_test)
        
        if not self.test_thread:
            self._log_to_monitor('创建测试线程失败', 'error')
            return

    def _run_test(self):
        try:
            self.real_time_monitor.start_monitoring()
            success = self.test_executor.execute_commands(self.test_commands)
            self.real_time_monitor.stop_monitoring()
            
            if success:
                self._log_to_monitor('测试完成', 'info')
                self._generate_report()
            else:
                self._log_to_monitor('测试失败', 'error')
        except Exception as e:
            self.console_logger.error(f'测试执行异常: {e}')
            self._log_to_monitor(f'测试执行异常: {e}', 'error')
            self.real_time_monitor.stop_monitoring()

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
    
    def _start_monitor(self):
        self.is_monitoring = True
        self.monitor_thread = self.thread_pool.submit(self._monitor_loop)

    def _monitor_loop(self):
        while self.is_monitoring:
            try:
                if self.chamber_controller:
                    temperature = self.chamber_controller.read_temperature()
                    if temperature is not None:
                        self.window['-CHAMBER_TEMP-'].update(f'{temperature:.1f}°C')
                
                if self.host_manager:
                    self._update_ssd_info()
                
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
            
            elif event == '-LOAD_SCRIPT-':
                self._load_script()
            
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


if __name__ == '__main__':
    import os
    
    app = NVMeTestGUI()
    app.run()
