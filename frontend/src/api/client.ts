/**
 * API 客户端基础封装
 * 
 * 功能：
 * 1. 统一的基础 URL 配置
 * 2. 统一的错误处理
 * 3. 统一的请求/响应拦截
 * 4. TypeScript 类型安全
 */

// API 基础 URL（开发环境）
const API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * 自定义 API 错误类
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * 处理 API 响应
 * 统一处理错误状态码和 JSON 解析
 */
async function handleResponse<T>(response: Response): Promise<T> {
  // 检查响应状态
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorDetail: any = null;

    try {
      // 尝试解析错误详情（FastAPI 返回的 JSON）
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
      errorDetail = errorData;
    } catch {
      // 如果无法解析 JSON，使用默认错误信息
    }

    throw new ApiError(response.status, errorMessage, errorDetail);
  }

  // 解析 JSON 响应
  try {
    const data = await response.json();
    return data as T;
  } catch (error) {
    throw new ApiError(500, 'Failed to parse response JSON', error);
  }
}

/**
 * 通用 API 请求函数
 * 
 * @param endpoint - API 端点（例如：'/nodes' 或 '/nodes/123'）
 * @param options - fetch 选项（method, body, headers 等）
 * @returns Promise<T> - 解析后的响应数据
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // 构建完整 URL
  const url = `${API_BASE_URL}${endpoint}`;

  // 默认请求头
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // 合并选项
  const requestOptions: RequestInit = {
    ...options,
    headers,
  };

  try {
    // 发送请求
    const response = await fetch(url, requestOptions);
    
    // 处理响应
    return await handleResponse<T>(response);
  } catch (error) {
    // 处理网络错误或其他异常
    if (error instanceof ApiError) {
      throw error;
    }
    
    // 网络错误或其他未知错误
    throw new ApiError(
      0,
      error instanceof Error ? error.message : 'Network error occurred',
      error
    );
  }
}

/**
 * GET 请求快捷方法
 */
export async function apiGet<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'GET' });
}

/**
 * POST 请求快捷方法
 */
export async function apiPost<T>(
  endpoint: string,
  data: any
): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * PUT 请求快捷方法
 */
export async function apiPut<T>(
  endpoint: string,
  data: any
): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * DELETE 请求快捷方法
 */
export async function apiDelete<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'DELETE' });
}

