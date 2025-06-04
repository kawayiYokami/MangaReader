const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { EventEmitter } = require('events');

/**
 * Python服务管理器
 * 负责启动、停止、监控Python后端服务
 */
class PythonServiceManager extends EventEmitter {
    constructor(config) {
        super();
        
        this.config = {
            scriptPath: config.scriptPath,
            port: config.port || 8080,
            isDev: config.isDev || false,
            maxRetries: config.maxRetries || 3,
            retryDelay: config.retryDelay || 2000,
            startupTimeout: config.startupTimeout || 30000
        };
        
        this.process = null;
        this.isRunning = false;
        this.retryCount = 0;
        this.logs = [];
        this.maxLogLines = 1000;
        
        console.log('🐍 PythonServiceManager initialized:', this.config);
    }

    /**
     * 启动Python服务
     */
    async start() {
        if (this.isRunning) {
            console.log('⚠️ Python服务已在运行');
            return true;
        }

        console.log('🚀 启动Python服务...');
        
        try {
            // 验证Python脚本存在
            await this.validatePythonScript();
            
            // 启动服务
            await this.spawnPythonProcess();
            
            // 等待服务就绪
            await this.waitForServiceReady();
            
            this.isRunning = true;
            this.retryCount = 0;
            this.emit('status-changed', 'running');
            
            console.log('✅ Python服务启动成功');
            return true;
            
        } catch (error) {
            console.error('❌ Python服务启动失败:', error);
            await this.handleStartupError(error);
            throw error;
        }
    }

    /**
     * 停止Python服务
     */
    async stop() {
        if (!this.isRunning || !this.process) {
            console.log('⚠️ Python服务未运行');
            return true;
        }

        console.log('🛑 停止Python服务...');
        
        return new Promise((resolve) => {
            const timeout = setTimeout(() => {
                console.log('⚠️ 强制终止Python进程');
                this.process.kill('SIGKILL');
                resolve();
            }, 5000);

            this.process.once('exit', () => {
                clearTimeout(timeout);
                this.cleanup();
                console.log('✅ Python服务已停止');
                resolve();
            });

            // 优雅关闭
            this.process.kill('SIGTERM');
        });
    }

    /**
     * 重启Python服务
     */
    async restart() {
        console.log('🔄 重启Python服务...');
        await this.stop();
        await new Promise(resolve => setTimeout(resolve, 1000));
        return await this.start();
    }

    /**
     * 获取服务状态
     */
    getStatus() {
        return {
            isRunning: this.isRunning,
            port: this.config.port,
            pid: this.process?.pid,
            retryCount: this.retryCount,
            uptime: this.process ? Date.now() - this.process.spawnTime : 0
        };
    }

    /**
     * 获取服务端口
     */
    getPort() {
        return this.config.port;
    }

    /**
     * 获取日志
     */
    getLogs() {
        return this.logs.slice(-100); // 返回最近100行日志
    }

    /**
     * 验证Python脚本存在
     */
    async validatePythonScript() {
        const scriptPath = this.config.scriptPath;
        
        if (!fs.existsSync(scriptPath)) {
            throw new Error(`Python脚本不存在: ${scriptPath}`);
        }
        
        console.log('✅ Python脚本验证通过:', scriptPath);
    }

    /**
     * 启动Python进程
     */
    async spawnPythonProcess() {
        const args = [
            this.config.scriptPath,
            '--port', this.config.port.toString()
        ];

        console.log('🐍 启动Python进程:', 'python', args.join(' '));

        this.process = spawn('python', args, {
            cwd: path.dirname(this.config.scriptPath),
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env }
        });

        this.process.spawnTime = Date.now();

        // 设置进程事件监听
        this.setupProcessEventHandlers();
    }

    /**
     * 设置进程事件处理器
     */
    setupProcessEventHandlers() {
        // 标准输出
        this.process.stdout.on('data', (data) => {
            const message = data.toString().trim();
            this.addLog('stdout', message);
            
            if (this.config.isDev) {
                console.log(`[Python] ${message}`);
            }
        });

        // 错误输出
        this.process.stderr.on('data', (data) => {
            const message = data.toString().trim();
            this.addLog('stderr', message);
            
            if (this.config.isDev) {
                console.error(`[Python Error] ${message}`);
            }
        });

        // 进程退出
        this.process.on('exit', (code, signal) => {
            console.log(`🐍 Python进程退出: code=${code}, signal=${signal}`);
            this.handleProcessExit(code, signal);
        });

        // 进程错误
        this.process.on('error', (error) => {
            console.error('🐍 Python进程错误:', error);
            this.emit('error', error);
        });
    }

    /**
     * 等待服务就绪
     */
    async waitForServiceReady() {
        const startTime = Date.now();
        const timeout = this.config.startupTimeout;
        
        while (Date.now() - startTime < timeout) {
            try {
                // 检查服务是否响应
                const response = await this.checkServiceHealth();
                if (response) {
                    console.log('✅ Python服务就绪');
                    return true;
                }
            } catch (error) {
                // 继续等待
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        throw new Error(`Python服务启动超时 (${timeout}ms)`);
    }

    /**
     * 检查服务健康状态
     */
    async checkServiceHealth() {
        const http = require('http');
        
        return new Promise((resolve, reject) => {
            const req = http.get(`http://127.0.0.1:${this.config.port}/`, (res) => {
                resolve(res.statusCode === 200);
            });
            
            req.on('error', reject);
            req.setTimeout(2000, () => {
                req.destroy();
                reject(new Error('Health check timeout'));
            });
        });
    }

    /**
     * 处理进程退出
     */
    handleProcessExit(code, signal) {
        this.cleanup();
        
        if (code !== 0 && this.retryCount < this.config.maxRetries) {
            console.log(`🔄 Python服务异常退出，准备重试 (${this.retryCount + 1}/${this.config.maxRetries})`);
            this.retryCount++;
            
            setTimeout(() => {
                this.start().catch(error => {
                    console.error('❌ 重试启动失败:', error);
                    this.emit('error', error);
                });
            }, this.config.retryDelay);
        } else {
            this.emit('status-changed', 'stopped');
        }
    }

    /**
     * 处理启动错误
     */
    async handleStartupError(error) {
        this.cleanup();
        this.emit('error', error);
    }

    /**
     * 清理资源
     */
    cleanup() {
        this.isRunning = false;
        this.process = null;
    }

    /**
     * 添加日志
     */
    addLog(type, message) {
        const timestamp = new Date().toISOString();
        this.logs.push({
            timestamp,
            type,
            message
        });
        
        // 限制日志数量
        if (this.logs.length > this.maxLogLines) {
            this.logs = this.logs.slice(-this.maxLogLines);
        }
    }
}

module.exports = PythonServiceManager;
