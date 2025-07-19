// /src/types/global.d.ts

/**
 * 定义从 Python 通过 pywebview.js_api 暴露给前端的函数。
 * 这提供了类型安全和自动补全。
 */
interface PywebviewApi {
  // 触发原生对话框以选择一个目录进行扫描
  trigger_select_directory: () => Promise<{ success: boolean; message: string }>;

  // 在系统的文件浏览器中打开并选中指定的文件
  open_in_explorer: (filePath: string) => Promise<{ success: boolean; message: string }>;

  // 可以为未来添加的其他API函数保留一个索引签名
  [key: string]: (...args: any[]) => Promise<any> | any;
}


// 通过 declare global 扩展全局 Window 接口
declare global {
  interface Window {
    // pywebview 是一个可选属性，因为它只在pywebview环境中存在
    pywebview?: {
      api: PywebviewApi;
    };
  }
}

// 导出一个空对象，以确保此文件被视为一个模块。
// 这是在使用 `declare global` 时的一个好习惯。
export {};