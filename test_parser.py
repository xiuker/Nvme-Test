from test_script_parser import TestScriptParser

# 创建解析器实例
parser = TestScriptParser()

# 解析测试脚本
try:
    commands = parser.parse_script('test_capacity_params.ini')
    print(f'成功解析 {len(commands)} 条命令:')
    for i, cmd in enumerate(commands, 1):
        print(f'{i}. {cmd.command_type} - {cmd.params}')
    
except Exception as e:
    print(f'解析错误: {e}')

# 验证脚本
try:
    valid, errors = parser.validate_script('test_capacity_params.ini')
    if valid:
        print('\n脚本验证通过!')
    else:
        print('\n脚本验证失败:')
        for error in errors:
            print(f'- {error}')
except Exception as e:
    print(f'验证错误: {e}')