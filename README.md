# NVMe SSD测试系统

## 系统概述

NVMe SSD测试系统是一个用于自动化测试NVMe固态硬盘的综合测试平台。该系统通过控制高低温试验箱和多台Linux测试主机，实现对SSD在各种温度条件下的性能和可靠性测试。

## 系统架构

### 硬件组成
- **Console主机**: Windows系统，运行测试软件
- **测试主机**: 若干台Linux系统，连接被测SSD
- **高低温试验箱**: 用于温度测试环境

### 软件组成
- **串口控制模块**: 控制高低温试验箱
- **SSH控制模块**: 远程控制测试主机
- **测试执行模块**: 执行PCT/BIT/CTTW/CTTR测试
- **结果分析模块**: 分析测试结果并生成报告
- **GUI界面**: PySimpleGUI实现的用户界面

## 功能特性

### 1. 串口控制温箱模块
- 支持两套温箱控制命令
- 实时温度监控
- 温度设定和保温功能
- 支持正负温度设定

### 2. SSD测试模块
- **PCT测试**: 开关机测试
- **BIT测试**: 老化测试（可设置测试容量百分比）
- **CTTW测试**: 跨温区写测试
- **CTTR测试**: 跨温区读测试
- 实时测试进度展示
- SSD信息一致性检查

### 3. 实时监控模块
- 温度实时监控
- 测试进度实时展示
- 日志记录和展示
- 统计信息面板

## 安装说明

### 环境要求
- Python 3.8+
- Windows 10/11 (Console主机)
- Linux (测试主机)
- PySimpleGUI 4.x

### 安装步骤

1. 克隆或下载项目代码

2. 安装Python依赖包
```bash
pip install -r requirements.txt
```

3. 配置系统参数
编辑 `config.ini` 文件，设置以下参数：
- 串口配置（端口、波特率等）
- 测试主机配置（IP地址、MAC地址等）
- SSH配置（用户名、密码等）
- 测试参数配置

4. 准备测试脚本
编辑 `test_script.ini` 文件，定义测试流程

## 使用说明

### 启动系统
```bash
python main.py
```

### 界面操作

#### 温箱控制
- **启动温箱**: 启动高低温试验箱
- **停止温箱**: 停止高低温试验箱
- **读取温度**: 读取当前温箱温度
- **设定温度**: 设定目标温度

#### 测试脚本
- **加载脚本**: 加载测试脚本文件
- **验证脚本**: 验证脚本语法和参数

#### 测试控制
- **开始测试**: 开始执行测试脚本
- **暂停测试**: 暂停当前测试
- **停止测试**: 停止测试并清理

#### 测试报告
- **生成HTML报告**: 生成测试结果HTML报告
- **打开报告**: 在浏览器中打开测试报告

## 测试脚本格式

测试脚本使用INI格式，支持以下命令：

### TEMP命令
设定温度并保温
```
TEMP <温度> <保温时间(秒)>
```

示例:
```
TEMP 25 100
TEMP -42 3600
TEMP 87 3600
```

### PCT命令
开关机测试
```
PCT <测试轮数>
```

示例:
```
PCT 10
PCT 100
```

### BIT命令
老化测试
```
BIT <测试容量百分比(1-100)>
```

示例:
```
BIT 1
BIT 100
```

### CTTW命令
跨温区写测试
```
CTTW
```

### CTTR命令
跨温区读测试
```
CTTR
```

### 完整示例
```
TEMP 25 10
PCT 10
BIT 1

TEMP -42 3600
PCT 100
BIT 100
CTTW

TEMP 87 3600
CTTR
PCT 100
BIT 100
CTTW

TEMP -42 3600
CTTR
PCT 100
BIT 100
CTTW

TEMP 87 3600
CTTR
PCT 100
BIT 100

TEMP 25 600
PCT 10
BIT 100
```

## 配置文件说明

### config.ini配置项

#### [serial] - 串口配置
- `port`: 串口号（如COM1）
- `baudrate`: 波特率（默认2400）
- `bytesize`: 数据位（默认8）
- `parity`: 校验位（默认N）
- `stopbits`: 停止位（默认1）
- `timeout`: 超时时间（默认2秒）

#### [chamber] - 温箱配置
- `command_set`: 命令集（1或2）
- `wait_time_after_start`: 启动后等待时间
- `wait_time_after_stop`: 停止后等待时间

#### [test_hosts] - 测试主机配置
- `host1_ip`: 主机1的IP地址
- `host1_mac`: 主机1的MAC地址
- `host1_name`: 主机1的名称

#### [ssh] - SSH配置
- `username`: SSH用户名（默认root）
- `password`: SSH密码（默认1）
- `port`: SSH端口（默认22）
- `connect_timeout`: 连接超时时间
- `command_timeout`: 命令执行超时时间

#### [pct] - PCT测试配置
- `wait_time_after_wol`: WOL唤醒后等待时间
- `wait_time_after_shutdown`: 关机后等待时间
- `fio_size`: FIO测试大小

#### [bit] - BIT测试配置
- `temperature_check_interval`: 温度检查间隔

#### [cttw] - CTTW测试配置
- `temperature_check_interval`: 温度检查间隔

#### [cttr] - CTTR测试配置
- `temperature_check_interval`: 温度检查间隔

#### [logging] - 日志配置
- `console_log_dir`: 控制台日志目录
- `test_log_dir`: 测试日志目录
- `max_log_size`: 最大日志文件大小
- `log_backup_count`: 日志备份数量

#### [analysis] - 分析配置
- `max_temperature`: 最高温度阈值
- `min_temperature`: 最低温度阈值

## 测试结果

### 日志文件
- **控制台日志**: `./console_log/log.txt`
- **测试日志**: `./nvme_test_log/<测试时间>/<SSD SN>/<文件名>.txt`

### 测试报告
- **HTML报告**: `./nvme_test_log/<测试时间>/report.html`
- 报告包含详细的测试结果、错误信息、温度曲线等

### 错误检测
系统会自动检测以下错误：
- SSD掉盘
- SSD识别异常
- 链路连接异常
- 测试温度过高/过低
- 数据校验失败

## 注意事项

1. **温箱控制**: 确保温箱串口连接正确，波特率设置匹配
2. **网络连接**: 确保Console主机与测试主机网络连通
3. **SSH配置**: 确保测试主机SSH服务正常运行，用户名密码正确
4. **WOL功能**: 确保测试主机支持Wake-on-LAN功能
5. **温度范围**: 温箱温度设置应在合理范围内（-50°C ~ 100°C）
6. **测试时间**: 某些测试（如BIT、CTTW、CTTR）可能需要较长时间

## 故障排除

### 串口连接失败
- 检查串口号是否正确
- 检查串口是否被其他程序占用
- 检查串口线连接

### SSH连接失败
- 检查网络连接
- 检查SSH服务是否启动
- 检查用户名密码是否正确

### WOL唤醒失败
- 检查MAC地址是否正确
- 检查网络是否支持广播
- 检查主机BIOS中WOL是否启用

### 测试失败
- 查看日志文件获取详细错误信息
- 检查SSD是否正确连接
- 检查fio工具是否安装

## 技术支持

如有问题，请查看日志文件或联系技术支持。

## 版本历史

- v1.0.0 - 初始版本
  - 实现基本的温箱控制功能
  - 实现PCT/BIT/CTTW/CTTR测试
  - 实现测试结果分析和HTML报告生成
  - 实现GUI界面和实时监控

## 许可证

本项目仅供内部使用。
