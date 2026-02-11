import unittest
from datetime import datetime
from test_summary_generator import TestSummaryGenerator

class TestTestSummaryGenerator(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.config = {
            'enable_summary': True,
            'include_temperature': True,
            'include_ssd_info': True
        }
        self.generator = TestSummaryGenerator(self.config)
        self.start_time = datetime.now()
        self.end_time = datetime.now()
        self.additional_info = {
            'MN': 'Samsung 970 EVO',
            'VID': 'Samsung',
            'DID': '1234'
        }
    
    def test_init(self):
        """测试初始化方法"""
        generator = TestSummaryGenerator(self.config)
        self.assertIsInstance(generator, TestSummaryGenerator)
    
    def test_generate_test_summary(self):
        """测试生成单个测试总结"""
        summary = self.generator.generate_test_summary(
            test_type='BIT',
            ssd_sn='1234567890',
            start_time=self.start_time,
            end_time=self.end_time,
            temperature=25.5,
            additional_info=self.additional_info
        )
        
        self.assertIsInstance(summary, str)
        self.assertIn('BIT测试总结', summary)
        self.assertIn('1234567890', summary)
        self.assertIn('25.5C', summary)
        self.assertIn('Samsung 970 EVO', summary)
        self.assertIn('Samsung', summary)
    
    def test_generate_batch_summaries(self):
        """测试批量生成总结"""
        test_results = [
            {
                'test_type': 'BIT',
                'ssd_sn': '1234567890',
                'start_time': self.start_time,
                'end_time': self.end_time,
                'temperature': 25.5,
                'additional_info': self.additional_info
            },
            {
                'test_type': 'CTTR',
                'ssd_sn': '0987654321',
                'start_time': self.start_time,
                'end_time': self.end_time,
                'temperature': 26.0,
                'additional_info': self.additional_info
            }
        ]
        
        summaries = self.generator.generate_batch_summaries(test_results)
        self.assertIsInstance(summaries, dict)
        self.assertEqual(len(summaries), 2)
        self.assertIn('BIT-1234567890', summaries)
        self.assertIn('CTTR-0987654321', summaries)
        self.assertIn('BIT测试总结', summaries['BIT-1234567890'])
        self.assertIn('CTTR测试总结', summaries['CTTR-0987654321'])
    
    def test_validate_summary(self):
        """测试验证总结功能"""
        summary = self.generator.generate_test_summary(
            test_type='BIT',
            ssd_sn='1234567890',
            start_time=self.start_time,
            end_time=self.end_time,
            temperature=25.5,
            additional_info=self.additional_info
        )
        
        validation_result = self.generator.validate_summary(summary, 'BIT')
        self.assertIsInstance(validation_result, dict)
        self.assertIn('valid', validation_result)
        self.assertIn('errors', validation_result)
    
    def test_validate_summary_invalid(self):
        """测试验证无效总结"""
        invalid_summary = "这是一个无效的总结"
        validation_result = self.generator.validate_summary(invalid_summary, 'BIT')
        self.assertIsInstance(validation_result, dict)
        self.assertIn('valid', validation_result)
        self.assertIn('errors', validation_result)
    
    def test_format_summary_content(self):
        """测试格式化总结内容"""
        content = "测试内容: {value}"
        formatted_content = self.generator.format_summary_content(content, value="测试值")
        self.assertIsInstance(formatted_content, str)
        self.assertIn('测试内容: 测试值', formatted_content)
    
    def test_get_summary_template(self):
        """测试获取总结模板"""
        template = self.generator.get_summary_template('BIT')
        self.assertIsInstance(template, str)
        self.assertIn('BIT测试总结', template)
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        # 测试默认配置加载
        generator = TestSummaryGenerator({})
        self.assertIsInstance(generator, TestSummaryGenerator)
    
    def test_generate_with_missing_info(self):
        """测试生成缺少信息的总结"""
        summary = self.generator.generate_test_summary(
            test_type='BIT',
            ssd_sn='1234567890',
            start_time=self.start_time,
            end_time=self.end_time,
            temperature=25.5,
            additional_info={}
        )
        
        self.assertIsInstance(summary, str)
        self.assertIn('BIT测试总结', summary)
        self.assertIn('1234567890', summary)
    
    def test_minimal_config(self):
        """测试最小配置"""
        config = {}
        generator = TestSummaryGenerator(config)
        
        summary = generator.generate_test_summary(
            test_type='BIT',
            ssd_sn='1234567890',
            start_time=self.start_time,
            end_time=self.end_time,
            temperature=25.5,
            additional_info=self.additional_info
        )
        
        self.assertIsInstance(summary, str)
        self.assertIn('BIT测试总结', summary)

if __name__ == '__main__':
    unittest.main()
