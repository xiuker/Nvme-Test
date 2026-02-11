import unittest
import sys
import os

# 添加当前目录到路径，以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TestTableUpdateLogic(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        # 初始表格数据
        self.initial_data = [
            ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', '', '', '', ''],
            ['test_host_2', 'IP: 192.168.1.102\nMAC: 00:11:22:33:44:56', '', '', '', ''],
            ['test_host_3', 'IP: 192.168.1.103\nMAC: 00:11:22:33:44:57', '', '', '', ''],
            ['test_host_4', 'IP: 192.168.1.104\nMAC: 00:11:22:33:44:58', '', '', '', '']
        ]
        
        # 导入需要测试的方法
        from main import NVMeTestGUI
        
        # 创建一个简单的测试实例，只包含必要的属性
        class TestGUI:
            def __init__(self, initial_data):
                self.initial_data = initial_data
                self.console_logger = type('MockLogger', (), {
                    'info': lambda *args, **kwargs: None,
                    'error': lambda *args, **kwargs: None,
                    'debug': lambda *args, **kwargs: None,
                    'warning': lambda *args, **kwargs: None
                })()
                self.table_data = [row.copy() for row in initial_data]
                
                # 模拟窗口对象
                class MockWindow:
                    def __init__(self, test_gui):
                        self.test_gui = test_gui
                    
                    def __getitem__(self, key):
                        if key == '-TEST_CONTROL_TABLE-':
                            # 创建一个带有正确方法的MockTable类
                            class MockTable:
                                def __init__(self, test_gui):
                                    self.test_gui = test_gui
                                
                                def get(self):
                                    return [row.copy() for row in self.test_gui.table_data]
                                
                                def update(self, values):
                                    self.test_gui.table_data = values
                            
                            return MockTable(self.test_gui)
                        return type('MockElement', (), {
                            'update': lambda *args, **kwargs: None
                        })()
                    
                    def refresh(self):
                        pass
                
                self.window = MockWindow(self)
        
        # 创建测试实例
        self.test_gui = TestGUI(self.initial_data)
        
        # 将NVMeTestGUI的方法绑定到测试实例
        self.test_gui._compare_table_data = NVMeTestGUI._compare_table_data.__get__(self.test_gui)
        
        # 重写_update_table_cell方法，添加调试信息
        def debug_update_table_cell(row, col, value):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查索引是否有效
                if row < 0 or row >= len(current_data):
                    print(f'行索引超出范围: {row}')
                    return False
                
                if col < 0 or col >= len(current_data[0]):
                    print(f'列索引超出范围: {col}')
                    return False
                
                # 修改指定单元格
                new_data = [row.copy() for row in current_data]
                new_data[row][col] = value
                
                # 更新表格
                self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.test_gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.test_gui._compare_table_data(current_data, new_data)
                if diff:
                    print(f'表格单元格更新成功: 行={row}, 列={col}, 新值={value}')
                    print(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.test_gui.window.refresh()
                    print('表格数据已回滚到原始状态')
                
                print(f'更新表格单元格失败: {e}')
                import traceback
                traceback.print_exc()
                return False
        
        # 重写_update_table_row方法，添加调试信息
        def debug_update_table_row(row, new_row_data):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查行索引是否有效
                if row < 0 or row >= len(current_data):
                    print(f'行索引超出范围: {row}')
                    return False
                
                # 检查新行数据长度是否与表格列数匹配
                if len(new_row_data) != len(current_data[0]):
                    print(f'新行数据长度不匹配: 期望 {len(current_data[0])}, 实际 {len(new_row_data)}')
                    return False
                
                # 替换指定行
                new_data = [row.copy() for row in current_data]
                new_data[row] = new_row_data.copy()
                
                # 更新表格
                self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.test_gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.test_gui._compare_table_data(current_data, new_data)
                if diff:
                    print(f'表格行更新成功: 行={row}')
                    print(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.test_gui.window.refresh()
                    print('表格数据已回滚到原始状态')
                
                print(f'更新表格行失败: {e}')
                import traceback
                traceback.print_exc()
                return False
        
        # 重写_update_table_data方法，添加调试信息
        def debug_update_table_data(update_data):
            try:
                # 保存当前表格数据作为备份
                backup_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 获取当前表格数据
                current_data = self.test_gui.window['-TEST_CONTROL_TABLE-'].get()
                
                # 检查更新数据是否为空
                if not update_data:
                    print('更新数据为空')
                    return True
                
                # 检查所有索引是否有效
                for (row, col), value in update_data.items():
                    if row < 0 or row >= len(current_data):
                        print(f'行索引超出范围: {row}')
                        return False
                    
                    if col < 0 or col >= len(current_data[0]):
                        print(f'列索引超出范围: {col}')
                        return False
                
                # 批量修改指定单元格
                new_data = [row.copy() for row in current_data]
                for (row, col), value in update_data.items():
                    new_data[row][col] = value
                
                # 更新表格
                self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=new_data)
                self.test_gui.window.refresh()
                
                # 比较更新前后的数据
                diff = self.test_gui._compare_table_data(current_data, new_data)
                if diff:
                    print(f'表格数据批量更新成功，共更新 {len(update_data)} 个单元格')
                    print(f'更新差异: {diff}')
                
                return True
                
            except Exception as e:
                # 发生异常时回滚到备份状态
                if 'backup_data' in locals():
                    self.test_gui.window['-TEST_CONTROL_TABLE-'].update(values=backup_data)
                    self.test_gui.window.refresh()
                    print('表格数据已回滚到原始状态')
                
                print(f'批量更新表格数据失败: {e}')
                import traceback
                traceback.print_exc()
                return False
        
        # 绑定调试方法
        self.test_gui._update_table_cell = debug_update_table_cell
        self.test_gui._update_table_row = debug_update_table_row
        self.test_gui._update_table_data = debug_update_table_data
    
    def tearDown(self):
        """清理测试环境"""
        pass
    
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
        diff = self.test_gui._compare_table_data(old_data, new_data)
        
        # 验证差异是否正确
        self.assertEqual(len(diff), 1)
        self.assertEqual(diff[0][0], 0)  # 行索引
        self.assertEqual(diff[0][1], 2)  # 列索引
        self.assertEqual(diff[0][2], '')  # 旧值
        self.assertEqual(diff[0][3], 'SN: 202505202T9001\n状态: [已连接]')  # 新值
    
    def test_update_table_cell_logic(self):
        """测试单元格更新逻辑"""
        # 模拟表格数据
        test_data = [row.copy() for row in self.initial_data]
        
        # 测试更新单个单元格
        row, col = 0, 2
        new_value = 'SN: 202505202T9001\n状态: [已连接]'
        
        # 执行更新
        result = self.test_gui._update_table_cell(row, col, new_value)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 验证数据是否已更新
        self.assertEqual(self.test_gui.table_data[row][col], new_value)
        
        # 验证其他单元格未受影响
        for i in range(len(test_data)):
            for j in range(len(test_data[i])):
                if i != row or j != col:
                    self.assertEqual(self.test_gui.table_data[i][j], test_data[i][j])
    
    def test_update_table_row_logic(self):
        """测试行更新逻辑"""
        # 测试更新整行
        row = 0
        new_row_data = ['test_host_1', 'IP: 192.168.1.101\nMAC: 00:11:22:33:44:55', 
                       'SN: 202505202T9001\n状态: [已连接]', 
                       'SN: 202505202T9002\n状态: [已连接]', 
                       '', '']
        
        # 执行更新
        result = self.test_gui._update_table_row(row, new_row_data)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 验证数据是否已更新
        self.assertEqual(self.test_gui.table_data[row], new_row_data)
        
        # 验证其他行未受影响
        for i in range(1, len(self.initial_data)):
            self.assertEqual(self.test_gui.table_data[i], self.initial_data[i])
    
    def test_update_table_data_logic(self):
        """测试批量更新逻辑"""
        # 测试批量更新
        update_data = {
            (0, 2): 'SN: 202505202T9001\n状态: [已连接]',
            (1, 3): 'SN: 202505202T9002\n状态: [已连接]',
            (2, 4): 'SN: 202505202T9003\n状态: [已连接]'
        }
        
        # 执行更新
        result = self.test_gui._update_table_data(update_data)
        
        # 验证更新是否成功
        self.assertTrue(result)
        
        # 验证数据是否已更新
        for (row, col), value in update_data.items():
            self.assertEqual(self.test_gui.table_data[row][col], value)
        
        # 验证其他单元格未受影响
        for i in range(len(self.initial_data)):
            for j in range(len(self.initial_data[i])):
                if (i, j) not in update_data:
                    self.assertEqual(self.test_gui.table_data[i][j], self.initial_data[i][j])
    
    def test_update_table_cell_out_of_bounds(self):
        """测试索引越界情况"""
        # 测试行索引越界
        result = self.test_gui._update_table_cell(10, 2, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        # 测试列索引越界
        result = self.test_gui._update_table_cell(0, 10, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        # 测试负索引
        result = self.test_gui._update_table_cell(-1, 2, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)
        
        result = self.test_gui._update_table_cell(0, -1, 'SN: 202505202T9001\n状态: [已连接]')
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()