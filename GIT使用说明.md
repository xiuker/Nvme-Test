# Git版本管理使用说明

## 快速开始

### 方法一：使用批处理脚本（推荐）

直接运行 `git_init.bat` 即可完成Git仓库初始化。

### 方法二：手动使用Git命令

在PowerShell中执行以下命令：

```powershell
# 设置Git路径
$env:GIT_PATH = "C:\Program Files\Git\cmd\git.exe"

# 初始化Git仓库
& $env:GIT_PATH init

# 添加所有文件
& $env:GIT_PATH add .

# 创建初始提交
& $env:GIT_PATH commit -m "初始版本：NVMe SSD测试系统 v1.0.0"

# 创建版本标签
& $env:GIT_PATH tag v1.0.0
```

## 常用Git命令

### 版本管理

```powershell
# 创建新版本
& $env:GIT_PATH tag v1.0.1 -m "版本说明"

# 查看所有版本
& $env:GIT_PATH tag

# 删除版本
& $env:GIT_PATH tag -d v1.0.1
```

### 提交代码

```powershell
# 添加修改的文件
& $env:GIT_PATH add .

# 提交更改
& $env:GIT_PATH commit -m "提交说明"

# 查看提交历史
& $env:GIT_PATH log --oneline

# 查看详细提交历史
& $env:GIT_PATH log --pretty=format:"%h - %an, %ar : %s"
```

### 版本回退

```powershell
# 回退到指定版本
& $env:GIT_PATH checkout v1.0.0

# 回退到指定提交
& $env:GIT_PATH checkout <commit-hash>

# 查看当前分支
& $env:GIT_PATH branch

# 创建新分支
& $env:GIT_PATH branch feature-xxx
```

### 查看状态

```powershell
# 查看当前状态
& $env:GIT_PATH status

# 查看文件修改
& $env:GIT_PATH diff

# 查看提交历史
& $env:GIT_PATH log --graph --all
```

## 版本管理最佳实践

1. **频繁提交**
   - 每完成一个功能或修复一个bug后立即提交
   - 提交信息要清晰描述做了什么

2. **使用版本标签**
   - 重要版本使用标签标记（如 v1.0.0）
   - 便于快速回退和查找

3. **写好提交信息**
   - 格式：`类型：简短描述`
   - 示例：`feat: 添加版本管理功能`
   - 示例：`fix: 修复主板选择bug`

4. **分支管理**
   - 开发新功能时创建新分支
   - 完成后合并到主分支

5. **定期备份**
   - 重要节点前创建版本标签
   - 便于快速回退

## 常见问题

### 提交失败
- 检查是否有未提交的修改
- 确保Git配置正确
- 检查文件权限

### 回退失败
- 确保版本标签存在
- 检查是否有未提交的修改
- 使用 `git status` 查看当前状态

## Git配置文件

项目已包含 `.gitignore` 文件，会自动忽略：
- Python缓存文件
- IDE配置文件
- 日志文件
- 测试结果
- 版本备份文件

## 示例工作流程

```powershell
# 1. 开发新功能
# 修改代码...

# 2. 提交代码
& $env:GIT_PATH add .
& $env:GIT_PATH commit -m "feat: 添加新功能"

# 3. 创建版本标签
& $env:GIT_PATH tag v1.0.1 -m "添加了XX功能"

# 4. 遇到bug需要回退
& $env:GIT_PATH checkout v1.0.0

# 5. 修复bug后重新提交
& $env:GIT_PATH add .
& $env:GIT_PATH commit -m "fix: 修复XX bug"

# 6. 创建新版本
& $env:GIT_PATH tag v1.0.2 -m "修复XX bug"
```

## 联系方式

如有问题，请查阅Git官方文档：
https://git-scm.com/docs
