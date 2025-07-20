/**
 * @description 前端性能计时器，用于测量和报告代码块的执行时间。
 */
export class PerformanceTimer {
    private timings: Map<string, number>;
    private startTimes: Map<string, number>;
    public traceId: string;

    constructor(traceId: string) {
        this.traceId = traceId;
        this.timings = new Map();
        this.startTimes = new Map();
    }

    /**
     * 开始一个计时阶段。
     * @param name 计时阶段的名称。
     */
    public start(name: string): void {
        this.startTimes.set(name, performance.now());
    }

    /**
     * 停止一个计时阶段并记录耗时。
     * @param name 计时阶段的名称。
     * @returns 返回该阶段的耗时（毫秒）。
     */
    public stop(name: string): number | undefined {
        if (this.startTimes.has(name)) {
            const startTime = this.startTimes.get(name)!;
            const elapsed = performance.now() - startTime;
            this.timings.set(name, elapsed);
            this.startTimes.delete(name);
            return elapsed;
        }
        console.warn(`Timer '${name}' was stopped without being started.`);
        return undefined;
    }

    /**
     * 获取指定阶段的耗时。
     * @param name 计时阶段的名称。
     * @returns 返回耗时（毫秒），如果不存在则返回 undefined。
     */
    public getTiming(name: string): number | undefined {
        return this.timings.get(name);
    }

    /**
     * 直接添加一个已计算好的耗时。
     * @param name 计时阶段的名称。
     * @param duration 耗时（毫秒）。
     */
    public addTiming(name: string, duration: number): void {
        this.timings.set(name, duration);
    }

    /**
     * 将所有计时日志作为一个整体打印到控制台。
     * @param overallStageName 报告的总体阶段名称。
     */
    public report(overallStageName: string): void {
        const totalElapsed = this.getTiming(overallStageName);
        if (totalElapsed === undefined) {
            console.warn(`Cannot generate report: overall stage '${overallStageName}' was not timed.`);
            return;
        }

        console.group(`%cPerformance Report for [${overallStageName}] - TraceID [${this.traceId}]`, 'color: #3498db; font-weight: bold;');
        console.log(`Total elapsed time: %c${totalElapsed.toFixed(2)} ms`, 'color: #e67e22; font-weight: bold;');
        
        this.timings.forEach((value, key) => {
            if (key !== overallStageName) {
                console.log(`  - [${key}] took %c${value.toFixed(2)} ms`, 'color: #2ecc71;');
            }
        });

        console.groupEnd();
    }
}