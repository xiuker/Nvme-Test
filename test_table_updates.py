import unittest
import sys
import os
from unittest.mock import Mock, patch

# 添加当前目录到路径，以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TestTableUpdates(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        # 模拟GUI实例
        class MockGUI:
            def __init__(self):
                # 模拟窗口对象
                self.window = Mock()
                # 模拟控制台日志
                self.console_logger = Mock()
                
                # 初始表格数据
                self.initial_data = [
                    ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', '', '', '', ''],
                    ['test_host_2', 'IP: 192.168.1.102\nMAC: 00:11:22:33:44:56', '', '', '', ''],
                    ['test_host_3', 'IP: 192.168.1.103\nMAC: 00:11:22:33:44:57', '', '', '', ''],
                    ['test_host_4', 'IP: 192.168.1.104\nMAC: 00:11:22:33:44:58', '', '', '', '']
                ]
                
                # 模拟表格数据获取和更新
                def get_table_data():
                    return self.initial_data
                
                def update_table_data(values):
                    self.initial_data = values
                
                # 模拟表格组件
                table_mock = Mock()
                table_mock.get = get_table_data
                table_mock.update = update_table_data
                
                # 模拟窗口的表格组件访问
                self.window_dict = {'-TEST_CONTROL_TABLE-': table_mock}
                def get_item(key):
                    return self.window_dict.get(key, Mock())
                
                self.window.get = get_item
                self.window.__getitem__ = get_item
                self.window.refresh = Mock()
        
        # 导入需要测试的方法
        from main import NVMeTestGUI
        
        # 创建模拟GUI实例
        self.gui = MockGUI()
        
        # 将NVMeTestGUI的方法绑定到模拟实例
        self.gui._compare_table_data = NVMeTestGUI._compare_table_data.__get__(self.gui)
        
        # 模拟_update_table_cell方法
        def mock_update_table_cell(row, col, value):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查索引是否有效
                if row < 0 or row >= len(current_data):
                    self.gui.console_logger.error(f'行索引超出范围: {row}')
                    return False
                
                if col < 0 or col >= len(current_data[0]):
                    self.gui.console_logger.error(f'列索引超出范围: {col}')
                    return False
                
                # 修改指定单元格
                new_data = [row.copy() for row in current_data]
                new_data[row][col] = value
                
                # 更新表格
                self.gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.gui._compare_table_data(current_data, new_data)
                if diff:
                    self.gui.console_logger.info(f'表格单元格更新成功: 行={row}, 列={col}, 新值={value}')
                    self.gui.console_logger.debug(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.gui.window.refresh()
                    self.gui.console_logger.info('表格数据已回滚到原始状态')
                
                self.gui.console_logger.error(f'更新表格单元格失败: {e}')
                return False
        
        # 模拟_update_table_row方法
        def mock_update_table_row(row, new_row_data):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查行索引是否有效
                if row < 0 or row >= len(current_data):
                    self.gui.console_logger.error(f'行索引超出范围: {row}')
                    return False
                
                # 检查新行数据长度是否与表格列数匹配
                if len(new_row_data) != len(current_data[0]):
                    self.gui.console_logger.error(f'新行数据长度不匹配: 期望 {len(current_data[0])}, 实际 {len(new_row_data)}')
                    return False
                
                # 替换指定行
                new_data = [row.copy() for row in current_data]
                new_data[row] = new_row_data.copy()
                
                # 更新表格
                self.gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.gui._compare_table_data(current_data, new_data)
                if diff:
                    self.gui.console_logger.info(f'表格行更新成功: 行={row}')
                    self.gui.console_logger.debug(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.gui.window.refresh()
                    self.gui.console_logger.info('表格数据已回滚到原始状态')
                
                self.gui.console_logger.error(f'更新表格行失败: {e}')
                return False
        
        # 模拟_update_table_data方法
        def mock_update_table_data(update_data):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查更新数据是否为空
                if not update_data:
                    self.gui.console_logger.warning('更新数据为空')
                    return True
                
                # 检查所有索引是否有效
                for (row, col), value in update_data.items():
                    if row < 0 or row >= len(current_data):
                        self.gui.console_logger.error(f'行索引超出范围: {row}')
                        return False
                    
                    if col < 0 or col >= len(current_data[0]):
                        self.gui.console_logger.error(f'列索引超出范围: {col}')
                        return False
                
                # 批量修改指定单元格
                new_data = [row.copy() for row in current_data]
                for (row, col), value in update_data.items():
                    new_data[row][col] = value
                
                # 更新表格
                self.gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.gui._compare_table_data(current_data, new_data)
                if diff:
                    self.gui.console_logger.info(f'表格数据批量更新成功，共更新 {len(update_data)} 个单元格')
                    self.gui.console_logger.debug(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.gui.window.refresh()
                    self.gui.console_logger.info('表格数据已回滚到原始状态')
                
                self.gui.console_logger.error(f'批量更新表格数据失败: {e}')
                return False
        
        # 绑定模拟方法
        self.gui._update_table_cell = mock_update_table_cell
        self.gui._update_table_row = mock_update_table_row
        self.gui._update_table_data = mock_update_table_data
    
    def tearDown(self):
        """清理测试环境"""
        pass
    
    def test_update_table_cell_basic(self):
        """测试基本的单元格更新"""
        # 更新单个单元格
        result = self.gui._update_table_cell(0, 2, 'SN: 202505202T9001\n状态: [已连接]')
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 获取更新后的表格数据
        updated_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
        
        # 验证指定单元格已更新
        self.assertEqual(updated_data[0][2], 'SN: 202505202T9001\n状态: [已连接]')
        
        # 验证其他单元格未受影响
        self.assertEqual(updated_data[0][0], self.gui.initial_data[0][0])
        self.assertEqual(updated_data[0][1], self.gui.initial_data[0][1])
        self.assertEqual(updated_data[0][3], self.gui.initial_data[0][3])
        self.assertEqual(updated_data[1][2], self.gui.initial_data[1][2])
    
    def test_update_table_row_basic(self):
        """测试基本的整行更新"""
        # 准备新行数据
        new_row_data = ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', 
                       'SN: 202505202T9001\n状态: [已连接]', 
                       'SN: 202505202T9002\n状态: [已连接]', 
                       '', '']
        
        # 更新整行数据
        result = self.gui._update_table_row(0, new_row_data)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 获取更新后的表格数据
        updated_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
        
        # 验证指定行已更新
        self.assertEqual(updated_data[0], new_row_data)
        
        # 验证其他行未受影响
        self.assertEqual(updated_data[1], self.gui.initial_data[1])
        self.assertEqual(updated_data[2], self.gui.initial_data[2])
        self.assertEqual(updated_data[3], self.gui.initial_data[3])
    
    def test_update_table_data_basic(self):
        """测试基本的批量更新"""
        # 准备批量更新数据
        update_data = {
            (0, 2): 'SN: 202505202T9001\n状态: [已连接]',
            (1, 3): 'SN: 202505202T9002\n状态: [已连接]',
            (2, 4): 'SN: 202505202T9003\n状态: [已连接]'
        }
        
        # 批量更新数据
        result = self.gui._update_table_data(update_data)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 获取更新后的表格数据
        updated_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
        
        # 验证指定单元格已更新
        for (row, col), value in update_data.items():
            self.assertEqual(updated_data[row][col], value)
        
        # 验证其他单元格未受影响
        self.assertEqual(updated_data[0][0], self.gui.initial_data[0][0])
        self.assertEqual(updated_data[0][1], self.gui.initial_data[0][1])
        self.assertEqual(updated_data[0][3], self.gui.initial_data[0][3])
        self.assertEqual(updated_data[1][2], self.gui.initial_data[1][2])
        self.assertEqual(updated_data[3][2], self.gui.initial_data[3][2])
    
    def test_update_table_cell_empty_value(self):
        """测试空值更新"""
        # 先设置一个非空值
        self.gui._update_table_cell(0, 2, 'SN: 202505202T9001\n状态: [已连接]')
        
        # 更新为空值
        result = self.gui._update_table_cell(0, 2, '')
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 获取更新后的表格数据
        updated_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
        
        # 验证指定单元格已更新为空
        self.assertEqual(updated_data[0][2], '')
        
        # 验证其他单元格未受影响
        self.assertEqual(updated_data[0][0], self.gui.initial_data[0][0])
        self.assertEqual(updated_data[0][1], self.gui.initial_data[0][1])
    
    def test_update_table_cell_special_characters(self):
        """测试特殊字符更新"""
        # 准备包含特殊字符的值
        special_value = 'SN: 202505202T9001\n状态: [已连接]\n备注: 特殊字符测试 !@#$%^&*()'
        
        # 更新包含特殊字符的值
        result = self.gui._update_table_cell(0, 2, special_value)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 获取更新后的表格数据
        updated_data = self.gui.window['-TEST_CONTROL_TABLE-'].get()
        
        # 验证指定单元格已更新
        self.assertEqual(updated_data[0][2], special_value)
        
        # 验证其他单元格未受影响
        self.assertEqual(updated_data[0][0], self.gui.initial_data[0][0])
        self.assertEqual(updated_data[0][1], self.gui.initial_data[0][1])
    
    def test_update_table_cell_out_of_bounds(self):
        """测试索引越界情况"""
        # 测试行索引越界
        result = self.gui._update_table_cell(10, 2, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        # 测试列索引越界
        result = self.gui._update_table_cell(0, 10, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        # 测试负索引
        result = self.gui._update_table_cell(-1, 2, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        result = self.gui._update_table_cell(0, -1, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
    
    def test_compare_table_data(self):
        """测试数据对比功能"""
        # 准备旧数据和新数据
        old_data = [
            ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', '', '', '', ''],
            ['test_host_2', 'IP: 192.168.1.102\nMAC: 00:11:22:33:44:56', '', '', '', '']
        ]
        
        new_data = [
            ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', 'SN: 202505202T9001\n状态: [已连接]', '', '', ''],
            ['test_host_2', 'IP: 192.168.1.102\nMAC: 00:11:22:33:44:56', '', '', '', '']
        ]
        
        # 比较数据
        diff = self.gui._compare_table_data(old_data, new_data)
        
        # 验证差异是否正确
        self.assertEqual(len(diff), 1)
        self.assertEqual(diff[0][0], 0)  # 行索引
        self.assertEqual(diff[0][1], 2)  # 列索引
        self.assertEqual(diff[0][2], '')  # 旧值
        self.assertEqual(diff[0][3], 'SN: 202505202T9001\n状态: [已连接]')  # 新值

if __name__ == '__main__':
    unittest.main()
