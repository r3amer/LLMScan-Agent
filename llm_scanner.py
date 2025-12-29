import tarfile
import os
import json
from google import genai
from typing import List, Dict, Any, Optional


class LLMScanner:
    SENSITIVE_PATTERNS = [
        "id_rsa", ".ssh", ".aws", ".kube", "credentials", "secret", 
        "config.json", "settings.py", ".env", ".pem", ".key", ".pfx",
        "passwd", "shadow", "authorized_keys"
    ]

    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("API 密钥不能为空。请提供有效的 Google GenAI API 密钥。")
            
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.system_instruction = (
            "你是一位专业的容器镜像安全专家，专注于识别文件中的敏感凭证。"
            "拥有专业的容器安全知识和丰富的凭证识别经验。"
            "你的回答必须且只能是有效的 JSON 格式，"
            "且不包含任何解释性文字或Markdown格式的JSON块标记（如 ```json ... ```）。"
        )
    
    def think(self, msg, system_instruction):
        config = {
            "system_instruction": system_instruction,
            "response_mime_type": "application/json",
        }
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=msg,
                config=config
            )
            return json.loads(response.text)
        except json.JSONDecodeError:
            print("警告: Gemini 模型未能输出有效的 JSON 格式。")
            return {"error": "JSON 解析失败", "raw_output": response.text}
        except Exception as e:
            return {"api call error": f"GenAI API 调用失败: {e}"}


    def is_sensitive_file(self, file_path: str) -> bool:
        path_lower = file_path.lower()
        
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in path_lower:
                return True
        return False

    def analyze_file_contents(self, file_content: str) -> Dict[str, Any]:
        if not file_content.strip():
            return {"secrets": [], "summary": "文件内容为空，无需分析。"}
        user_prompt = (
            f"请严格按照系统指令中的JSON格式要求，分析以下文件内容。识别所有类型的有效敏感凭证（如API密钥、数据库密码、SSH私钥、Access Key等），注意忽略其中无效的凭证，比如用来占位的环境变量或类似example这样的示例凭证等"
            f"并为每个凭证的值提供类型、大致位置（例如：行号或配置键名）和凭证片段（Value Snippet）。如果存在敏感凭证，summary中需要包含用法。\n\n"
            "JSON 结构必须是: {\"secrets\": [{\"value\": \"...\", \"credential_type\": \"...\", \"location\": \"...\"}], \"summary\": \"...\"}。如果未发现敏感凭证，必须返回空值。"
            "API密钥类型的value中需要包含API密钥值以及API地址；密码类型的value中需要包含用户名和密码；SSH私钥类型的value必须包含用户名、SSH连接地址和私钥值；以此类推，任何类型的敏感凭证都必须包含使用该凭证所必须的信息，如果没有找到，就将该位置置空。"
            f"文件内容:\n---\n{file_content}\n---"
        )
        return self.think(user_prompt, self.system_instruction)

    def analyze_filenames(self, filenames: str, max_file_size: int = 5 * 1024 * 1024) -> Dict[str, Any]:
        user_prompt = (
            "我输入的数据包含镜像layer的部分文件名，你需要根据经验和网络搜索结果判断其中输入中可能包含敏感凭证的文件名并输出。"
            "回答中严禁包含输入中不存在的文件名"
            "回答的JSON 结构必须是: {\"{layerid_1}\": [\"{filename}\"], \"{layerid_2}\": [\"{filename}\"], ...}。"
            "如果未找到凭证，应为空。"
            f"以下是输入：{filenames}"
        )
        return self.think(user_prompt, self.system_instruction)


if __name__ == '__main__':
    scanner = LLMScanner(api_key="", model_name="gemini-2.5-flash")
    print(scanner.think(""))