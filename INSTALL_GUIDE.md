# 依赖库安装指南

## 使用清华镜像源安装依赖

### 方法一：使用批处理脚本（推荐）

直接运行 `install_dependencies.bat` 脚本即可自动安装所有依赖库。

### 方法二：手动使用清华镜像源

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 方法三：永久配置清华镜像源

创建 `pip.ini` 文件，内容如下：

```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple

[install]
trusted-host = pypi.tuna.tsinghua.edu.cn
```

然后使用以下命令安装：

```bash
pip install -r requirements.txt
```

## 依赖库列表

- PySimpleGUI-4-foss==4.60.4.1
- paramiko==4.0.0
- pyserial==3.5
- pywin32==311
- configparser==7.2.0
- matplotlib==3.10.8
- numpy==2.4.1
- psutil==7.2.1

## 清华镜像源优势

- 速度快：国内镜像源，下载速度快
- 稳定可靠：清华大学官方镜像，稳定可靠
- 自动同步：与PyPI官方同步，版本最新
- 免费使用：完全免费，无需额外配置

## 其他常用镜像源

如果清华镜像源不可用，可以尝试以下镜像：

1. 阿里云镜像：`https://mirrors.aliyun.com/pypi/simple/`
2. 豆瓣镜像：`https://pypi.douban.com/simple/`
3. 腾讯云镜像：`https://mirrors.cloud.tencent.com/pypi/simple/`

## 验证安装

安装完成后，可以使用以下命令验证：

```bash
pip list
```

查看所有已安装的库和版本。
