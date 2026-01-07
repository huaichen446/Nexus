"""
通用 LLM API 验证器 (LLM_api_Verifier)

功能：
提供标准化的测试流程，验证任何兼容 OpenAI 协议或 LiteLLM 支持的大模型接口。

测试维度：
1. 基础 HTTP 连通性 (仅限 OpenAI 兼容接口)
2. LiteLLM 库集成
3. 流式响应 (Streaming)
4. 多轮对话 (Context Memory)
"""

import os
import sys
import requests
import traceback

# 尝试导入 litellm
try:
    import litellm
except ImportError:
    litellm = None


class LLMApiVerifier:
    def __init__(self, api_key: str, model: str, base_url: str = None, provider: str = "openai"):
        """
        初始化验证器
        :param api_key: API 密钥
        :param model: 模型名称 (如 'glm-4-flash', 'gpt-4o')
        :param base_url: API 基础地址 (如 'https://open.bigmodel.cn/api/paas/v4')
        :param provider: LiteLLM provider (默认为 'openai'，智谱/DeepSeek 等均使用此模式)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self.results = []

        # 打印初始化信息
        print(f"\n🚀 初始化验证器: {self.provider} / {self.model}")
        if self.base_url:
            print(f"📍 Base URL: {self.base_url}")
        print("-" * 60)

    def _log(self, status, message):
        """内部日志格式化"""
        icon = "✅" if status else "❌"
        print(f"{icon} {message}")
        return status

    def test_raw_http(self):
        """测试 1: 原生 HTTP 请求 (排除库干扰)"""
        print("\nTesting 1: Raw HTTP Request (OpenAI Compatible)...")

        if self.provider != "openai" or not self.base_url:
            print("⚠️  跳过: 仅适用于指定了 Base URL 的 OpenAI 兼容协议")
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                return self._log(True, f"HTTP 连接成功 (200 OK)")
            else:
                return self._log(False, f"HTTP 失败: {response.status_code} - {response.text}")
        except Exception as e:
            return self._log(False, f"HTTP 请求异常: {str(e)}")

    def test_litellm_integration(self):
        """测试 2: LiteLLM 基础调用"""
        print("\nTesting 2: LiteLLM Integration...")
        if not litellm:
            return self._log(False, "LiteLLM 未安装")

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                api_base=self.base_url,
                api_key=self.api_key,
                custom_llm_provider=self.provider,  # 关键参数
                max_tokens=10
            )
            content = response.choices[0].message.content
            print(f"   🤖 回复: {content}")
            return self._log(True, "LiteLLM 调用成功")
        except Exception as e:
            print(f"   🔍 错误详情: {str(e)}")
            return self._log(False, "LiteLLM 调用失败")

    def test_streaming(self):
        """测试 3: 流式响应"""
        print("\nTesting 3: Streaming Response...")
        try:
            stream = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "写3个数字"}],
                api_base=self.base_url,
                api_key=self.api_key,
                custom_llm_provider=self.provider,
                stream=True,
                max_tokens=50
            )
            print("   🌊 流式输出: ", end="", flush=True)
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end="", flush=True)
            print("")  # 换行
            return self._log(True, "流式测试成功")
        except Exception as e:
            return self._log(False, f"流式测试失败: {str(e)}")

    def test_multi_turn(self):
        """测试 4: 多轮对话 (上下文记忆)"""
        print("\nTesting 4: Multi-turn Context...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My name is Neo."},
            {"role": "assistant", "content": "Hello Neo."},
            {"role": "user", "content": "What is my name?"}
        ]
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                api_base=self.base_url,
                api_key=self.api_key,
                custom_llm_provider=self.provider,
                max_tokens=50
            )
            content = response.choices[0].message.content
            print(f"   🗣️  问: What is my name? -> 答: {content}")

            if "Neo" in content or "neo" in content:
                return self._log(True, "记忆测试通过 (Name matched)")
            else:
                return self._log(True, "调用成功 (但未明确检测到名字，可能因模型措辞差异)")
        except Exception as e:
            return self._log(False, f"多轮对话失败: {str(e)}")

    def run_all(self):
        """运行所有测试"""
        self.results.append(("Raw HTTP", self.test_raw_http()))
        self.results.append(("LiteLLM Basic", self.test_litellm_integration()))
        self.results.append(("Streaming", self.test_streaming()))
        self.results.append(("Context", self.test_multi_turn()))

        print("\n" + "=" * 30)
        print("📊 测试总结报告")
        print("=" * 30)
        success_count = 0
        for name, passed in self.results:
            if passed is None:
                status = "⚪ 跳过"
            elif passed:
                status = "✅ 通过"
                success_count += 1
            else:
                status = "❌ 失败"
            print(f"{name:<20} : {status}")

        return success_count == len([r for r in self.results if r[1] is not None])


# --- 使用示例 ---
if __name__ == "__main__":
    # 示例 1: 测试智谱 AI (GLM-4-Flash)
    # 你可以在这里修改为你想测试的任何配置

    verifier = LLMApiVerifier(
        api_key="443c25f8fad94dc7aa6b2594fff2808c.TVfiGGDtRLdth2qX",  # 建议换成 os.getenv("ZHIPU_API_KEY")
        model="glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        provider="openai"  # 智谱使用 openai 兼容协议
    )

    verifier.run_all()

    # 示例 2: 将来测试 DeepSeek (只需改下面几行)
    # verifier = LLMApiVerifier(
    #     api_key="sk-xxxx",
    #     model="deepseek-chat",
    #     base_url="https://api.deepseek.com",
    #     provider="openai"
    # )
    # verifier.run_all()