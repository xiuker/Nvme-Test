# git config --global user.name "hqs"
# git config --global user.email "1578557654@qq.com"
# git config --global init.defaultBranch main
@echo off
chcp 65001
set GIT_PATH=C:\Program Files\Git\cmd\git.exe

echo 正在初始化Git仓库...
%GIT_PATH% init

echo 正在添加文件到暂存区...
%GIT_PATH% add .

echo 正在创建初始提交...
%GIT_PATH% commit -m "初始版本：NVMe SSD测试系统 v1.0.0"

echo 正在创建版本标签...
%GIT_PATH% tag v1.0.0

echo.
echo Git仓库初始化完成！
echo.
echo 使用说明：
echo   创建版本：git tag v1.0.1 -m "版本说明"
echo   查看版本：git tag
echo   查看历史：git log --oneline
echo   回退版本：git checkout v1.0.0
echo.
pause
