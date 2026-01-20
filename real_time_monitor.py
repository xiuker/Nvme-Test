import threading
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import numpy as np

from logger import ConsoleLogger


class RealTimeMonitor:
    def __init__(self, logger: Optional[ConsoleLogger] = None):
        self.logger = logger
        self.is_monitoring = False
        self.monitor_thread = None
        self.data_callbacks = []
        self.temperature_data = {}
        self.test_progress_data = []
        self.max_data_points = 100

    def add_data_callback(self, callback: Callable):
        self.data_callbacks.append(callback)

    def start_monitoring(self, interval: int = 5):
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
        
        if self.logger:
            self.logger.info('实时监控已启动')

    def stop_monitoring(self):
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        if self.logger:
            self.logger.info('实时监控已停止')

    def _monitor_loop(self, interval: int):
        while self.is_monitoring:
            try:
                timestamp = datetime.now()
                
                for callback in self.data_callbacks:
                    callback(timestamp)
                
                time.sleep(interval)
            except Exception as e:
                if self.logger:
                    self.logger.error(f'监控循环异常: {e}')
                time.sleep(interval)

    def add_temperature_data(self, ssd_id: str, temperature: float, timestamp: datetime):
        if ssd_id not in self.temperature_data:
            self.temperature_data[ssd_id] = {
                'timestamps': [],
                'temperatures': []
            }
        
        data = self.temperature_data[ssd_id]
        data['timestamps'].append(timestamp)
        data['temperatures'].append(temperature)
        
        if len(data['timestamps']) > self.max_data_points:
            data['timestamps'] = data['timestamps'][-self.max_data_points:]
            data['temperatures'] = data['temperatures'][-self.max_data_points:]

    def add_progress_data(self, command_index: int, total_commands: int, 
                         cycle_index: int, total_cycles: int, 
                         current_test_item: str, timestamp: datetime):
        progress_entry = {
            'timestamp': timestamp,
            'command_index': command_index,
            'total_commands': total_commands,
            'cycle_index': cycle_index,
            'total_cycles': total_cycles,
            'current_test_item': current_test_item
        }
        
        self.test_progress_data.append(progress_entry)
        
        if len(self.test_progress_data) > self.max_data_points:
            self.test_progress_data = self.test_progress_data[-self.max_data_points:]

    def get_temperature_data(self, ssd_id: str) -> Dict:
        return self.temperature_data.get(ssd_id, {'timestamps': [], 'temperatures': []})

    def get_progress_data(self) -> List[Dict]:
        return self.test_progress_data


class TemperatureChart:
    def __init__(self, parent_frame, monitor: RealTimeMonitor, logger: Optional[ConsoleLogger] = None):
        self.monitor = monitor
        self.logger = logger
        self.parent_frame = parent_frame
        
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.lines = {}
        self.animation = None
        self.is_active = False

    def start_animation(self):
        if self.is_active:
            return
        
        self.is_active = True
        self.animation = animation.FuncAnimation(
            self.fig, self.update_chart, interval=1000, blit=False
        )
        self.canvas.draw()
        
        if self.logger:
            self.logger.info('温度图表动画已启动')

    def stop_animation(self):
        self.is_active = False
        if self.animation:
            self.animation.event_source.stop()
        
        if self.logger:
            self.logger.info('温度图表动画已停止')

    def update_chart(self, frame):
        self.ax.clear()
        
        self.ax.set_title('SSD温度监控', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('时间')
        self.ax.set_ylabel('温度 (°C)')
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        for ssd_id, data in self.monitor.temperature_data.items():
            if data['timestamps'] and data['temperatures']:
                timestamps = [ts for ts in data['timestamps']]
                temperatures = [temp for temp in data['temperatures']]
                
                line, = self.ax.plot(timestamps, temperatures, label=ssd_id, marker='o', markersize=3)
                self.lines[ssd_id] = line
        
        if self.monitor.temperature_data:
            self.ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
        
        self.fig.tight_layout()
        self.canvas.draw()

    def set_temperature_limits(self, min_temp: float, max_temp: float):
        self.ax.set_ylim(min_temp - 5, max_temp + 5)
        self.ax.axhline(y=max_temp, color='r', linestyle='--', alpha=0.7, label=f'最高温度阈值: {max_temp}°C')
        self.ax.axhline(y=min_temp, color='b', linestyle='--', alpha=0.7, label=f'最低温度阈值: {min_temp}°C')


class ProgressChart:
    def __init__(self, parent_frame, monitor: RealTimeMonitor, logger: Optional[ConsoleLogger] = None):
        self.monitor = monitor
        self.logger = logger
        self.parent_frame = parent_frame
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.animation = None
        self.is_active = False

    def start_animation(self):
        if self.is_active:
            return
        
        self.is_active = True
        self.animation = animation.FuncAnimation(
            self.fig, self.update_chart, interval=1000, blit=False
        )
        self.canvas.draw()
        
        if self.logger:
            self.logger.info('进度图表动画已启动')

    def stop_animation(self):
        self.is_active = False
        if self.animation:
            self.animation.event_source.stop()
        
        if self.logger:
            self.logger.info('进度图表动画已停止')

    def update_chart(self, frame):
        self.ax1.clear()
        self.ax2.clear()
        
        if not self.monitor.test_progress_data:
            return
        
        timestamps = [entry['timestamp'] for entry in self.monitor.test_progress_data]
        command_progress = [entry['command_index'] / entry['total_commands'] * 100 
                           if entry['total_commands'] > 0 else 0 
                           for entry in self.monitor.test_progress_data]
        
        cycle_data = {}
        for entry in self.monitor.test_progress_data:
            test_item = entry['current_test_item']
            if test_item not in cycle_data:
                cycle_data[test_item] = {
                    'timestamps': [],
                    'cycle_progress': []
                }
            
            cycle_data[test_item]['timestamps'].append(entry['timestamp'])
            cycle_progress = entry['cycle_index'] / entry['total_cycles'] * 100 \
                            if entry['total_cycles'] > 0 else 0
            cycle_data[test_item]['cycle_progress'].append(cycle_progress)
        
        self.ax1.plot(timestamps, command_progress, 'b-', linewidth=2, label='命令进度')
        self.ax1.set_title('测试命令进度', fontsize=14, fontweight='bold')
        self.ax1.set_xlabel('时间')
        self.ax1.set_ylabel('进度 (%)')
        self.ax1.set_ylim(0, 105)
        self.ax1.grid(True, linestyle='--', alpha=0.7)
        self.ax1.legend()
        
        for test_item, data in cycle_data.items():
            if data['timestamps'] and data['cycle_progress']:
                self.ax2.plot(data['timestamps'], data['cycle_progress'], 
                             marker='o', markersize=3, label=test_item)
        
        self.ax2.set_title('测试轮次进度', fontsize=14, fontweight='bold')
        self.ax2.set_xlabel('时间')
        self.ax2.set_ylabel('进度 (%)')
        self.ax2.set_ylim(0, 105)
        self.ax2.grid(True, linestyle='--', alpha=0.7)
        self.ax2.legend()
        
        self.fig.tight_layout()
        self.canvas.draw()


class StatisticsPanel:
    def __init__(self, parent_frame, monitor: RealTimeMonitor, logger: Optional[ConsoleLogger] = None):
        self.monitor = monitor
        self.logger = logger
        self.parent_frame = parent_frame
        
        self.stats_frame = tk.Frame(parent_frame)
        self.stats_frame.pack(fill=tk.BOTH, expand=True)
        
        self.temp_stats = {}
        self.test_stats = {
            'total_commands': 0,
            'completed_commands': 0,
            'current_test_item': '无',
            'total_cycles': 0,
            'completed_cycles': 0,
            'start_time': None,
            'elapsed_time': 0
        }
        
        self._create_widgets()

    def _create_widgets(self):
        title_label = tk.Label(self.stats_frame, text="统计信息", 
                              font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        self.temp_frame = tk.LabelFrame(self.stats_frame, text="温度统计", padx=10, pady=10)
        self.temp_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.test_frame = tk.LabelFrame(self.stats_frame, text="测试统计", padx=10, pady=10)
        self.test_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.temp_labels = {}
        temp_items = ['当前温度', '最高温度', '最低温度', '平均温度']
        
        for item in temp_items:
            frame = tk.Frame(self.temp_frame)
            frame.pack(fill=tk.X, pady=2)
            
            label = tk.Label(frame, text=f"{item}:", width=12, anchor='w')
            label.pack(side=tk.LEFT)
            
            value_label = tk.Label(frame, text="N/A", width=10, anchor='w', 
                                  font=('Arial', 10, 'bold'))
            value_label.pack(side=tk.LEFT)
            
            self.temp_labels[item] = value_label
        
        self.test_labels = {}
        test_items = ['总命令数', '已完成命令', '当前测试项', '总轮次数', 
                     '已完成轮次', '开始时间', '已用时间']
        
        for item in test_items:
            frame = tk.Frame(self.test_frame)
            frame.pack(fill=tk.X, pady=2)
            
            label = tk.Label(frame, text=f"{item}:", width=12, anchor='w')
            label.pack(side=tk.LEFT)
            
            value_label = tk.Label(frame, text="N/A", width=15, anchor='w', 
                                  font=('Arial', 10, 'bold'))
            value_label.pack(side=tk.LEFT)
            
            self.test_labels[item] = value_label

    def update_statistics(self):
        self._update_temperature_stats()
        self._update_test_stats()

    def _update_temperature_stats(self):
        for ssd_id, data in self.monitor.temperature_data.items():
            if data['temperatures']:
                current_temp = data['temperatures'][-1]
                max_temp = max(data['temperatures'])
                min_temp = min(data['temperatures'])
                avg_temp = sum(data['temperatures']) / len(data['temperatures'])
                
                self.temp_labels['当前温度'].config(text=f"{current_temp:.1f}°C")
                self.temp_labels['最高温度'].config(text=f"{max_temp:.1f}°C")
                self.temp_labels['最低温度'].config(text=f"{min_temp:.1f}°C")
                self.temp_labels['平均温度'].config(text=f"{avg_temp:.1f}°C")
                
                break

    def _update_test_stats(self):
        if self.monitor.test_progress_data:
            latest = self.monitor.test_progress_data[-1]
            
            self.test_labels['总命令数'].config(text=str(latest['total_commands']))
            self.test_labels['已完成命令'].config(text=str(latest['command_index']))
            self.test_labels['当前测试项'].config(text=latest['current_test_item'])
            self.test_labels['总轮次数'].config(text=str(latest['total_cycles']))
            self.test_labels['已完成轮次'].config(text=str(latest['cycle_index']))
            
            if self.monitor.test_progress_data:
                start_time = self.monitor.test_progress_data[0]['timestamp']
                self.test_labels['开始时间'].config(text=start_time.strftime('%H:%M:%S'))
                
                elapsed = datetime.now() - start_time
                hours, remainder = divmod(elapsed.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.test_labels['已用时间'].config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")


class RealTimeMonitorWindow:
    def __init__(self, parent, monitor: RealTimeMonitor, logger: Optional[ConsoleLogger] = None):
        self.parent = parent
        self.monitor = monitor
        self.logger = logger
        
        self.window = tk.Toplevel(parent)
        self.window.title("实时监控")
        self.window.geometry("1200x800")
        
        self._create_widgets()
        self._setup_callbacks()

    def _create_widgets(self):
        notebook = tk.Frame(self.window)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        self.temp_frame = tk.Frame(notebook)
        self.progress_frame = tk.Frame(notebook)
        self.stats_frame = tk.Frame(notebook)
        
        self.temp_frame.pack(fill=tk.BOTH, expand=True)
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        self.stats_frame.pack(fill=tk.BOTH, expand=True)
        
        self.temp_chart = TemperatureChart(self.temp_frame, self.monitor, self.logger)
        self.progress_chart = ProgressChart(self.progress_frame, self.monitor, self.logger)
        self.stats_panel = StatisticsPanel(self.stats_frame, self.monitor, self.logger)
        
        button_frame = tk.Frame(self.window)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = tk.Button(button_frame, text="开始监控", 
                                     command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(button_frame, text="停止监控", 
                                    command=self.stop_monitoring)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = tk.Button(button_frame, text="刷新统计", 
                                       command=self.refresh_statistics)
        self.refresh_button.pack(side=tk.LEFT, padx=5)

    def _setup_callbacks(self):
        self.monitor.add_data_callback(self.on_data_update)

    def on_data_update(self, timestamp: datetime):
        self.stats_panel.update_statistics()

    def start_monitoring(self):
        self.monitor.start_monitoring()
        self.temp_chart.start_animation()
        self.progress_chart.start_animation()

    def stop_monitoring(self):
        self.monitor.stop_monitoring()
        self.temp_chart.stop_animation()
        self.progress_chart.stop_animation()

    def refresh_statistics(self):
        self.stats_panel.update_statistics()

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def hide(self):
        self.window.withdraw()

    def close(self):
        self.stop_monitoring()
        self.window.destroy()
