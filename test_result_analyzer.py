import os
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from logger import ConsoleLogger


class TestResultAnalyzer:
    def __init__(self, config: Dict, logger: Optional[ConsoleLogger] = None):
        self.config = config
        self.logger = logger
        self.analysis_config = config.get('analysis', {})
        self.max_temperature = self.analysis_config.get('max_temperature', 85)
        self.min_temperature = self.analysis_config.get('min_temperature', -45)

    def analyze_test_result(self, test_time: str, test_log_dir: str) -> Dict:
        analysis_result = {
            'test_time': test_time,
            'ssd_results': {},
            'overall_status': 'PASS',
            'error_count': 0,
            'warning_count': 0
        }
        
        test_time_dir = os.path.join(test_log_dir, test_time)
        
        if not os.path.exists(test_time_dir):
            if self.logger:
                self.logger.error(f'测试日志目录不存在: {test_time_dir}')
            return analysis_result
        
        for ssd_sn in os.listdir(test_time_dir):
            ssd_dir = os.path.join(test_time_dir, ssd_sn)
            
            if os.path.isdir(ssd_dir):
                ssd_result = self._analyze_ssd_results(ssd_sn, ssd_dir, test_time)
                analysis_result['ssd_results'][ssd_sn] = ssd_result
                
                if ssd_result['status'] == 'FAIL':
                    analysis_result['overall_status'] = 'FAIL'
                    analysis_result['error_count'] += ssd_result['error_count']
                
                analysis_result['warning_count'] += ssd_result['warning_count']
        
        return analysis_result

    def _analyze_ssd_results(self, ssd_sn: str, ssd_dir: str, test_time: str) -> Dict:
        ssd_result = {
            'ssd_sn': ssd_sn,
            'status': 'PASS',
            'errors': [],
            'warnings': [],
            'test_items': {},
            'error_count': 0,
            'warning_count': 0
        }
        
        error_file = os.path.join(ssd_dir, f'{test_time}-{ssd_sn}-error.txt')
        
        if os.path.exists(error_file):
            with open(error_file, 'r', encoding='utf-8') as f:
                error_content = f.read()
            
            error_sections = error_content.split('-' * 50)
            
            for section in error_sections:
                if section.strip():
                    error_info = self._parse_error_section(section)
                    if error_info:
                        ssd_result['errors'].append(error_info)
                        ssd_result['error_count'] += 1
        
        for filename in os.listdir(ssd_dir):
            if filename.startswith(test_time) and filename.endswith('.txt'):
                test_item = self._extract_test_item_from_filename(filename)
                
                if test_item and test_item not in ['info', 'smart', 'temperature', 'error']:
                    filepath = os.path.join(ssd_dir, filename)
                    test_result = self._analyze_test_item(filepath, test_item)
                    ssd_result['test_items'][test_item] = test_result
                    
                    if test_result['status'] == 'FAIL':
                        ssd_result['status'] = 'FAIL'
                    
                    if test_result['warnings']:
                        ssd_result['warnings'].extend(test_result['warnings'])
                        ssd_result['warning_count'] += len(test_result['warnings'])
        
        temp_file = os.path.join(ssd_dir, f'{test_time}-{ssd_sn}-temperature.txt')
        
        if os.path.exists(temp_file):
            temp_analysis = self._analyze_temperature_data(temp_file)
            ssd_result['temperature_analysis'] = temp_analysis
            
            if temp_analysis['max_temp'] > self.max_temperature:
                ssd_result['status'] = 'FAIL'
                ssd_result['errors'].append({
                    'type': 'TEMPERATURE_HIGH',
                    'message': f'最高温度{temp_analysis["max_temp"]}°C超过阈值{self.max_temperature}°C',
                    'timestamp': temp_analysis['max_temp_time']
                })
                ssd_result['error_count'] += 1
            
            if temp_analysis['min_temp'] < self.min_temperature:
                ssd_result['status'] = 'FAIL'
                ssd_result['errors'].append({
                    'type': 'TEMPERATURE_LOW',
                    'message': f'最低温度{temp_analysis["min_temp"]}°C低于阈值{self.min_temperature}°C',
                    'timestamp': temp_analysis['min_temp_time']
                })
                ssd_result['error_count'] += 1
        
        if ssd_result['error_count'] > 0:
            ssd_result['status'] = 'FAIL'
        
        return ssd_result

    def _parse_error_section(self, section: str) -> Optional[Dict]:
        error_info = {}
        
        lines = section.strip().split('\n')
        
        for line in lines:
            if line.startswith('错误类型:'):
                error_info['type'] = line.split(':', 1)[1].strip()
            elif line.startswith('错误信息:'):
                error_info['message'] = line.split(':', 1)[1].strip()
            elif line.startswith('错误时间:'):
                error_info['timestamp'] = line.split(':', 1)[1].strip()
        
        if 'type' in error_info and 'message' in error_info:
            return error_info
        
        return None

    def _extract_test_item_from_filename(self, filename: str) -> Optional[str]:
        parts = filename.split('-')
        
        if len(parts) >= 4:
            test_item = parts[2]
            return test_item
        
        return None

    def _analyze_test_item(self, filepath: str, test_item: str) -> Dict:
        test_result = {
            'test_item': test_item,
            'status': 'PASS',
            'warnings': []
        }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '退出状态: 0' not in content:
            test_result['status'] = 'FAIL'
        
        if 'error' in content.lower() or 'fail' in content.lower():
            test_result['warnings'].append('测试输出中包含错误或失败信息')
        
        if 'verify' in content.lower() and 'fail' in content.lower():
            test_result['status'] = 'FAIL'
            test_result['warnings'].append('数据校验失败')
        
        if test_item == 'PCT':
            pct_analysis = self._analyze_pct_result(content)
            test_result.update(pct_analysis)
        
        return test_result

    def _analyze_pct_result(self, content: str) -> Dict:
        result = {}
        
        cycle_match = re.search(r'第(\d+)轮', content)
        if cycle_match:
            result['cycle'] = int(cycle_match.group(1))
        
        io_match = re.search(r'IOPS\s*:\s*([\d.]+[kK]?)', content)
        if io_match:
            result['iops'] = io_match.group(1)
        
        bw_match = re.search(r'bw\s*[:=]\s*([\d.]+[KMGT]?B/s)', content, re.IGNORECASE)
        if bw_match:
            result['bandwidth'] = bw_match.group(1)
        
        lat_match = re.search(r'lat\s*\([^)]+\)\s*[:=]\s*([\d.]+[mu]s)', content, re.IGNORECASE)
        if lat_match:
            result['latency'] = lat_match.group(1)
        
        return result

    def _analyze_temperature_data(self, filepath: str) -> Dict:
        temp_analysis = {
            'temperatures': [],
            'max_temp': -999,
            'min_temp': 999,
            'avg_temp': 0,
            'max_temp_time': '',
            'min_temp_time': ''
        }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            if ':' in line and '°C' in line:
                try:
                    temp_str = line.split('°C')[0].split(':')[-1].strip()
                    temp = float(temp_str)
                    timestamp = line.split(':')[0] + ':' + line.split(':')[1]
                    
                    temp_analysis['temperatures'].append(temp)
                    
                    if temp > temp_analysis['max_temp']:
                        temp_analysis['max_temp'] = temp
                        temp_analysis['max_temp_time'] = timestamp
                    
                    if temp < temp_analysis['min_temp']:
                        temp_analysis['min_temp'] = temp
                        temp_analysis['min_temp_time'] = timestamp
                
                except (ValueError, IndexError):
                    continue
        
        if temp_analysis['temperatures']:
            temp_analysis['avg_temp'] = sum(temp_analysis['temperatures']) / len(temp_analysis['temperatures'])
        
        return temp_analysis

    def check_ssd_disconnection(self, ssd_info_initial: Dict, ssd_info_current: Dict) -> List[Dict]:
        errors = []
        
        for sn in ssd_info_initial:
            if sn not in ssd_info_current:
                errors.append({
                    'type': 'SSD_DISCONNECTED',
                    'message': f'SSD {sn} 掉盘',
                    'ssd_sn': sn
                })
        
        return errors

    def check_ssd_recognition(self, ssd_info: Dict) -> List[Dict]:
        errors = []
        
        for sn, info in ssd_info.items():
            if not info.get('MN') or not info.get('SN'):
                errors.append({
                    'type': 'SSD_NOT_RECOGNIZED',
                    'message': f'SSD {sn} 识别不完整',
                    'ssd_sn': sn,
                    'info': info
                })
        
        return errors

    def check_link_status(self, link_status: Dict) -> List[Dict]:
        errors = []
        
        link = link_status.get('link', '').lower()
        speed = link_status.get('speed', '').lower()
        
        if 'gen3' not in link and 'gen3' not in speed:
            errors.append({
                'type': 'LINK_STATUS_ERROR',
                'message': f'链路状态异常: {link_status}',
                'link_status': link_status
            })
        
        return errors

    def generate_summary_report(self, analysis_result: Dict) -> str:
        summary = f'测试结果分析报告\n'
        summary += f'='*50 + '\n'
        summary += f'测试时间: {analysis_result["test_time"]}\n'
        summary += f'总体状态: {analysis_result["overall_status"]}\n'
        summary += f'错误数量: {analysis_result["error_count"]}\n'
        summary += f'警告数量: {analysis_result["warning_count"]}\n'
        summary += f'测试SSD数量: {len(analysis_result["ssd_results"])}\n\n'
        
        pass_count = sum(1 for ssd in analysis_result["ssd_results"].values() if ssd["status"] == "PASS")
        fail_count = sum(1 for ssd in analysis_result["ssd_results"].values() if ssd["status"] == "FAIL")
        
        summary += f'通过SSD数量: {pass_count}\n'
        summary += f'失败SSD数量: {fail_count}\n\n'
        
        summary += '详细结果:\n'
        summary += '-'*50 + '\n'
        
        for ssd_sn, ssd_result in analysis_result["ssd_results"].items():
            summary += f'\nSSD SN: {ssd_sn}\n'
            summary += f'状态: {ssd_result["status"]}\n'
            summary += f'错误数: {ssd_result["error_count"]}\n'
            summary += f'警告数: {ssd_result["warning_count"]}\n'
            
            if ssd_result["errors"]:
                summary += '错误列表:\n'
                for error in ssd_result["errors"]:
                    summary += f'  - [{error["type"]}] {error["message"]}\n'
            
            if ssd_result["warnings"]:
                summary += '警告列表:\n'
                for warning in ssd_result["warnings"]:
                    summary += f'  - {warning}\n'
            
            if 'temperature_analysis' in ssd_result:
                temp = ssd_result['temperature_analysis']
                summary += f'温度分析: 最高{temp["max_temp"]}°C, 最低{temp["min_temp"]}°C, 平均{temp["avg_temp"]:.1f}°C\n'
        
        return summary
