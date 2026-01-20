# 项目结构说明

## 文件组织结构

```
nvme_test_system/
├── config.ini                      # 系统配置文件
├── test_script.ini                 # 测试脚本示例
├── requirements.txt                # Python依赖包列表
├── README.md                       # 项目说明文档
├── PROJECT_STRUCTURE.md            # 本文件 - 项目结构说明
│
├── logger.py                       # 日志记录模块
│   ├── ConsoleLogger               # 控制台日志记录器
│   └── TestResultLogger           # 测试结果日志记录器
│
├── chamber_controller.py           # 温箱控制模块
│   ├── CRC16Modbus               # CRC16校验算法
│   └── ChamberController          # 温箱控制器（支持两套命令）
│
├── test_host_manager.py           # 测试主机管理模块
│   ├── TestHost                  # 单个测试主机控制
│   ├── WakeOnLAN                 # Wake-on-LAN唤醒功能
│   └── TestHostManager           # 多主机管理器
│
├── test_script_parser.py          # 测试脚本解析模块
│   ├── TestCommand               # 测试命令类
│   ├── TestScriptParser          # 测试脚本解析器
│   └── TestConfigParser         # 配置文件解析器
│
├── test_executor.py              # 测试执行模块
│   ├── TestProgress             # 测试进度跟踪
│   └── TestExecutor             # 测试执行器
│       ├── execute_temp_command      # 执行温度命令
│       ├── execute_pct_command      # 执行PCT测试
│       ├── execute_bit_command      # 执行BIT测试
│       ├── execute_cttw_command     # 执行CTTW测试
│       └── execute_cttr_command     # 执行CTTR测试
│
├── test_result_analyzer.py       # 测试结果分析模块
│   └── TestResultAnalyzer       # 测试结果分析器
│       ├── analyze_test_result          # 分析测试结果
│       ├── check_ssd_disconnection     # 检查SSD掉盘
│       ├── check_ssd_recognition      # 检查SSD识别
│       ├── check_link_status          # 检查链路状态
│       └── generate_summary_report    # 生成摘要报告
│
├── html_report_generator.py      # HTML报告生成模块
│   └── HTMLReportGenerator     # HTML报告生成器
│
├── real_time_monitor.py         # 实时监控模块
│   ├── RealTimeMonitor         # 实时监控核心
│   ├── TemperatureChart        # 温度图表
│   ├── ProgressChart          # 进度图表
│   ├── StatisticsPanel        # 统计面板
│   └── RealTimeMonitorWindow  # 实时监控窗口
│
├── main.py                     # 主程序入口
│   └── NVMeTestGUI            # 主界面类
│
├── console_log/                # 控制台日志目录（自动创建）
│   └── log.txt                # 控制台日志文件
│
└── nvme_test_log/              # 测试日志目录（自动创建）
    └── <测试时间>/            # 按测试时间分类
        └── <SSD SN>/          # 按SSD序列号分类
            ├── <测试时间>-<SSD SN>-info.txt        # SSD基本信息
            ├── <测试时间>-<SSD SN>-smart.txt       # SMART信息
            ├── <测试时间>-<SSD SN>-temperature.txt # 温度数据
            ├── <测试时间>-<SSD SN>-error.txt      # 错误日志
            ├── <测试时间>-<SSD SN>-PCT-<温度>C.txt # PCT测试结果
            ├── <测试时间>-<SSD SN>-BIT-<温度>C.txt # BIT测试结果
            ├── <测试时间>-<SSD SN>-CTTW-<温度>C.txt # CTTW测试结果
            ├── <测试时间>-<SSD SN>-CTTR-<温度>C.txt # CTTR测试结果
            └── report.html      # HTML测试报告
```

## 模块依赖关系

```
main.py (主程序)
  ├── logger.py
  ├── chamber_controller.py
  ├── test_host_manager.py
  ├── test_script_parser.py
  ├── test_executor.py
  │   ├── logger.py
  │   ├── chamber_controller.py
  │   └── test_host_manager.py
  ├── test_result_analyzer.py
  │   └── logger.py
  ├── html_report_generator.py
  │   └── logger.py
  └── real_time_monitor.py
      └── logger.py
```

## 核心功能模块说明

### 1. 日志记录模块 (logger.py)
- **ConsoleLogger**: 控制台日志记录，支持日志轮转
- **TestResultLogger**: 测试结果日志记录，按SSD序列号分类存储

### 2. 温箱控制模块 (chamber_controller.py)
- 支持两套温箱控制命令（Modbus协议和自定义协议）
- CRC16校验算法
- 温度设定、读取、启动、停止功能
- 温度等待和保温功能

### 3. 测试主机管理模块 (test_host_manager.py)
- SSH远程连接和控制
- Wake-on-LAN唤醒功能
- SSD信息获取（MN、SN、VID、DID）
- SSD链路状态检查
- SSD温度监控
- FIO测试执行

### 4. 测试脚本解析模块 (test_script_parser.py)
- INI格式测试脚本解析
- 支持TEMP、PCT、BIT、CTTW、CTTR命令
- 配置文件解析
- 脚本验证功能

### 5. 测试执行模块 (test_executor.py)
- 测试流程控制
- SSD信息一致性检查
- 温度监控线程
- 测试进度跟踪
- 支持暂停/恢复/停止

### 6. 测试结果分析模块 (test_result_analyzer.py)
- 测试结果分析
- 错误检测（掉盘、识别异常、链路异常、温度异常）
- 温度数据分析
- 摘要报告生成

### 7. HTML报告生成模块 (html_report_generator.py)
- 生成美观的HTML测试报告
- 包含图表和统计数据
- 支持打印和导出

### 8. 实时监控模块 (real_time_monitor.py)
- 实时温度监控图表
- 测试进度图表
- 统计信息面板
- 支持动画刷新

### 9. 主界面模块 (main.py)
- PySimpleGUI实现的用户界面
- 温箱控制面板
- 测试脚本管理
- 测试控制
- 实时监控日志
- SSD信息展示

## 数据流说明

### 测试执行流程
1. **加载测试脚本** → test_script_parser.py解析脚本
2. **初始化硬件** → chamber_controller.py和test_host_manager.py初始化
3. **执行测试命令** → test_executor.py执行具体测试
4. **记录测试数据** → logger.py记录测试结果
5. **分析测试结果** → test_result_analyzer.py分析结果
6. **生成测试报告** → html_report_generator.py生成HTML报告

### 实时监控流程
1. **启动监控** → real_time_monitor.py启动监控线程
2. **数据采集** → 定期采集温度和进度数据
3. **数据更新** → 更新图表和统计面板
4. **界面刷新** → main.py更新GUI显示

## 配置文件说明

### config.ini
- 串口配置
- 温箱配置
- 测试主机配置
- SSH配置
- 测试参数配置
- 日志配置
- 分析配置

### test_script.ini
- 测试流程定义
- 支持TEMP、PCT、BIT、CTTW、CTTR命令
- 可自定义测试参数

## 扩展性说明

### 添加新的测试类型
1. 在test_script_parser.py中添加新命令解析
2. 在test_executor.py中添加执行函数
3. 在test_result_analyzer.py中添加结果分析

### 添加新的温箱协议
1. 在chamber_controller.py中添加新的命令集
2. 更新配置文件中的command_set参数

### 添加新的报告格式
1. 创建新的报告生成器类
2. 在main.py中集成新的报告生成器

## 注意事项

1. 所有Python文件使用UTF-8编码
2. 变量命名使用蛇形命名法（snake_case）
3. 类名使用驼峰命名法（CamelCase）
4. 常量使用全大写命名法（UPPER_CASE）
5. 所有模块都有日志记录功能
6. 支持多线程操作，注意线程安全

## 性能优化建议

1. 大量SSD测试时，考虑使用线程池
2. 温度监控数据量大时，考虑使用数据库存储
3. HTML报告生成可以考虑使用模板引擎
4. 实时监控图表可以考虑使用更高效的绘图库

## 安全建议

1. SSH密码应加密存储
2. 串口操作应有超时保护
3. 测试命令应有权限控制
4. 日志文件应定期清理
