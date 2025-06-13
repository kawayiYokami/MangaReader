@echo off
chcp 65001
setlocal EnableDelayedExpansion

:: 设置 Git 相关的环境变量
set "LANG=zh_CN.UTF-8"
set "LANGUAGE=zh_CN.UTF-8"
set "LC_ALL=zh_CN.UTF-8"

:: =======================================================================
:: 调试辅助：脚本开始时强制暂停，以便查看初始错误
:: =======================================================================
echo 脚本开始执行...请按任意键继续。
pause
:: =======================================================================


:: =======================================================================
:: 配置部分 - 请根据你的实际情况修改以下变量
:: =======================================================================
:: 子项目配置
set "SUB_PROJECT_REPO=https://github.com/jingsongliujing/OnnxOCR.git"
set "SUB_PROJECT_DIR=OnnxOCR"
:: -----------------------------------------------------------------------

echo 正在检查 Git 是否安装并可用...
where git
if %errorlevel% neq 0 (
    echo 错误：未找到 Git。请确保 Git 已安装并已添加到系统 PATH。
    echo.
    echo 脚本将退出。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo 正在处理子项目: '%SUB_PROJECT_DIR%'
echo ============================================================
call :ProcessSubProject "%SUB_PROJECT_REPO%" "%SUB_PROJECT_DIR%"
if %errorlevel% neq 0 (
    echo.
    echo 遇到错误，请查看上方信息。
    pause
    exit /b 1
)

echo.
echo 按任意键完成所有子项目操作...
pause

echo.
echo ============================================================
echo 所有子项目操作完成。
echo ============================================================
echo.

pause
exit /b 0

:: =======================================================================
:: 子函数：处理单个子项目的克隆或更新
:: 参数1: 仓库URL
:: 参数2: 本地目录名
:: =======================================================================
:ProcessSubProject
set "REPO_URL=%~1"
set "TARGET_DIR=%~2"

echo.
echo 正在处理目录: '%TARGET_DIR%'

if exist "%TARGET_DIR%" (
    echo 目标文件夹 '%TARGET_DIR%' 已存在。尝试更新...
    pushd "%TARGET_DIR%"
    if %errorlevel% neq 0 (
        echo 错误：无法进入目录 '%TARGET_DIR%'。请检查权限或路径。
        exit /b 1
    )

    if not exist ".git" (
        echo 错误：'%TARGET_DIR%' 存在但不是一个 Git 仓库。
        echo 请手动删除该文件夹并重新运行此脚本。
        popd
        exit /b 1
    )

    echo 执行 git pull...
    set "GIT_REDIRECT_STDERR=2>&1"
    git -c i18n.logoutputencoding=utf-8 -c core.quotepath=false -c gui.encoding=utf-8 pull
    if %errorlevel% neq 0 (
        echo 错误：更新子项目 '%TARGET_DIR%' 失败。请检查网络连接或分支冲突。
        popd
        exit /b 1
    )

    echo 子项目 '%TARGET_DIR%' 已成功更新。
    popd

) else (
    echo 目标文件夹 '%TARGET_DIR%' 不存在，开始克隆子项目...
    set "GIT_REDIRECT_STDERR=2>&1"
    git -c i18n.logoutputencoding=utf-8 -c core.quotepath=false -c gui.encoding=utf-8 clone "%REPO_URL%" "%TARGET_DIR%"
    if %errorlevel% neq 0 (
        echo 错误：克隆子项目 '%TARGET_DIR%' 失败。请检查网络连接或仓库地址。
        exit /b 1
    )
    echo 子项目 '%TARGET_DIR%' 已成功克隆。
)
exit /b 0