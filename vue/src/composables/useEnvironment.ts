import { ref, readonly } from 'vue';

// 使用 ref 创建一个响应式的、模块级别的单例
const isPyWebView = ref(false);

// 在模块首次加载时执行一次检测逻辑
// 确保在客户端环境中执行
if (typeof window !== 'undefined' && typeof navigator !== 'undefined') {
  // 现代浏览器和WebView2支持 navigator.userAgentData
  const uaData = (navigator as Navigator & { userAgentData?: { brands: Array<{ brand: string; version: string }> } }).userAgentData;

  if (uaData && Array.isArray(uaData.brands)) {
    // 新标准：检查 brands 数组是否包含 "Microsoft Edge WebView2"
    isPyWebView.value = uaData.brands.some(
      (b: { brand: string; version: string }) => b.brand === "Microsoft Edge WebView2"
    );
  } else {
    // 后备方案：对于不支持 userAgentData 的环境，检查 userAgent 字符串
    isPyWebView.value = /WebView2/.test(navigator.userAgent);
  }
}

/**
 * @description 一个可组合函数，提供关于当前运行环境的信息。
 * @returns {{isPyWebView: Readonly<Ref<boolean>>}} 一个包含只读响应式引用的对象，
 * 指示当前是否在 PyWebView (WebView2) 环境中。
 */
export function useEnvironment() {
  return {
    isPyWebView: readonly(isPyWebView)
  };
}
