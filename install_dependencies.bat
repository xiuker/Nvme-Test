@echo off
chcp 65001
echo 正在使用清华镜像源安装依赖库...
echo.

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 安装失败，请检查网络连接或错误信息
) else (
    echo.
    echo 依赖库安装成功！
)

echo.
pause
