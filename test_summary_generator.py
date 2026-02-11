import os
from datetime import datetime
from typing import Dict, List, Optional, Any


class TestSummaryGenerator:
    """测试总结生成器
    
    用于生成标准化的测试总结，支持不同测试类型，提供配置选项和验证机制。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化测试总结生成器
        
        Args:
            config: 配置字典，可覆盖默认配置
        """
        # 默认配置
        self.default_config = {
            'enable_summary': True,
            'format_template': 'standard',
            'include_timestamp': True,
            'include_duration': True,
            'include_temperature': True,
            'include_test_type': True,
            'include_ssd_info': True,
            'time_format': '%Y-%m-%d %H:%M:%S',
            'temperature_unit': 'C',
            'min_summary_length': 100,
            'max_summary_length': 1000,
            'summary_template': {
                'header': '============================================================\n',
                'footer': '============================================================\n',
                'test_type_line': '{test_type}测试总结\n',
                'end_time_line': '测试结束时间: {end_time}\n',
                'duration_line': '测试总耗时: {duration:.2f}秒\n',
                'temperature_line': '测试温度: {temperature}{unit}\n',
                'ssd_info_line': 'SSD SN: {ssd_sn}\n',
                'additional_info_line': '{key}: {value}\n'
            }
        }
        
        # 合并配置
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
            # 处理嵌套配置
            if 'summary_template' in config:
                self.config['summary_template'].update(config['summary_template'])
    
    def generate_test_summary(self, test_type: str, ssd_sn: str, start_time: datetime, 
                           end_time: datetime, temperature: float, 
                           additional_info: Optional[Dict[str, Any]] = None) -> str:
        """生成单个测试总结
        
        Args:
            test_type: 测试类型（如PCT、BIT、CTTW、CTTR）
            ssd_sn: SSD序列号
            start_time: 测试开始时间
            end_time: 测试结束时间
            temperature: 测试温度
            additional_info: 额外信息字典
            
        Returns:
            生成的测试总结内容
        """
        if not self.config['enable_summary']:
            return ''
        
        # 计算测试时长
        test_duration = (end_time - start_time).total_seconds()
        
        # 获取模板
        template = self.config['summary_template']
        
        # 构建总结内容
        summary_content = template['header']
        
        # 添加测试类型
        if self.config['include_test_type']:
            summary_content += template['test_type_line'].format(test_type=test_type)
        
        # 添加测试结束时间
        if self.config['include_timestamp']:
            formatted_end_time = end_time.strftime(self.config['time_format'])
            summary_content += template['end_time_line'].format(end_time=formatted_end_time)
        
        # 添加测试总耗时
        if self.config['include_duration']:
            summary_content += template['duration_line'].format(duration=test_duration)
        
        # 添加测试温度
        if self.config['include_temperature']:
            unit = self.config['temperature_unit']
            summary_content += template['temperature_line'].format(
                temperature=temperature, 
                unit=unit
            )
        
        # 添加SSD信息
        if self.config['include_ssd_info']:
            summary_content += template['ssd_info_line'].format(ssd_sn=ssd_sn)
        
        # 添加额外信息
        if additional_info:
            summary_content += '\n额外信息:\n'
            for key, value in additional_info.items():
                summary_content += template['additional_info_line'].format(key=key, value=value)
        
        summary_content += template['footer']
        
        # 验证总结
        validation_result = self.validate_summary(summary_content, test_type)
        if not validation_result['valid']:
            # 记录验证错误，但仍然返回生成的总结
            print(f"警告: 生成的总结未通过验证: {validation_result['errors']}")
        
        return summary_content
    
    def generate_batch_summaries(self, test_summaries: List[Dict[str, Any]]) -> Dict[str, str]:
        """批量生成多个测试总结
        
        Args:
            test_summaries: 测试总结配置列表，每个元素包含生成单个总结所需的参数
            
        Returns:
            生成的测试总结字典，键为测试标识符，值为总结内容
        """
        summaries = {}
        
        for summary_config in test_summaries:
            # 生成总结
            summary_content = self.generate_test_summary(
                test_type=summary_config['test_type'],
                ssd_sn=summary_config['ssd_sn'],
                start_time=summary_config['start_time'],
                end_time=summary_config['end_time'],
                temperature=summary_config['temperature'],
                additional_info=summary_config.get('additional_info')
            )
            
            # 生成标识符
            identifier = f"{summary_config['test_type']}-{summary_config['ssd_sn']}"
            summaries[identifier] = summary_content
        
        return summaries
    
    def validate_summary(self, summary_content: str, test_type: str) -> Dict[str, Any]:
        """验证生成的总结是否符合标准
        
        Args:
            summary_content: 生成的总结内容
            test_type: 测试类型
            
        Returns:
            验证结果字典，包含valid和errors字段
        """
        result = {
            'valid': True,
            'errors': []
        }
        
        # 验证长度
        length = len(summary_content)
        if length < self.config['min_summary_length']:
            result['valid'] = False
            result['errors'].append(f"总结长度不足，当前: {length}, 最小: {self.config['min_summary_length']}")
        
        if length > self.config['max_summary_length']:
            result['valid'] = False
            result['errors'].append(f"总结长度过长，当前: {length}, 最大: {self.config['max_summary_length']}")
        
        # 验证必需内容
        required_contents = [
            f"{test_type}测试总结",
            "测试结束时间",
            "测试总耗时"
        ]
        
        for content in required_contents:
            if content not in summary_content:
                result['valid'] = False
                result['errors'].append(f"缺少必需内容: {content}")
        
        # 验证格式
        template = self.config['summary_template']
        if template['header'] not in summary_content:
            result['valid'] = False
            result['errors'].append("缺少标准头部格式")
        
        if template['footer'] not in summary_content:
            result['valid'] = False
            result['errors'].append("缺少标准尾部格式")
        
        return result
    
    def format_summary_content(self, content: str, **kwargs) -> str:
        """格式化总结内容
        
        Args:
            content: 原始内容
            **kwargs: 格式化参数
            
        Returns:
            格式化后的内容
        """
        return content.format(**kwargs)
    
    def get_summary_template(self, test_type: str) -> str:
        """获取指定测试类型的总结模板
        
        Args:
            test_type: 测试类型
            
        Returns:
            总结模板字符串
        """
        template = self.config['summary_template']
        
        template_content = template['header']
        template_content += template['test_type_line'].format(test_type=test_type)
        template_content += template['end_time_line'].replace('{end_time}', '{end_time}')
        template_content += template['duration_line'].replace('{duration:.2f}', '{duration}')
        template_content += template['temperature_line'].replace('{temperature}', '{temperature}').replace('{unit}', self.config['temperature_unit'])
        template_content += template['ssd_info_line'].replace('{ssd_sn}', '{ssd_sn}')
        template_content += template['footer']
        
        return template_content
    
    def save_summary_to_file(self, summary_content: str, file_path: str, append: bool = False) -> bool:
        """保存总结到文件
        
        Args:
            summary_content: 总结内容
            file_path: 文件路径
            append: 是否追加模式
            
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 写入文件
            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(summary_content)
            
            return True
        except Exception as e:
            print(f"保存总结到文件失败: {e}")
            return False
    
    def load_config_from_file(self, config_file: str) -> bool:
        """从文件加载配置
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            是否加载成功
        """
        try:
            if not os.path.exists(config_file):
                return False
            
            # 简单的配置文件解析（可根据实际格式扩展）
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 处理不同类型的配置
                        if key in ['enable_summary', 'include_timestamp', 'include_duration', 
                                 'include_temperature', 'include_test_type', 'include_ssd_info']:
                            self.config[key] = value.lower() == 'true'
                        elif key in ['min_summary_length', 'max_summary_length']:
                            self.config[key] = int(value)
                        elif key == 'time_format':
                            self.config[key] = value
                        elif key == 'temperature_unit':
                            self.config[key] = value
            
            return True
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return False
