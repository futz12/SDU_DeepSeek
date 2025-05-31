from typing import Generator, Iterable
import requests
import json


url = "https://aiassist.sdu.edu.cn/site/ai/compose_chat"


class ChatSession:
    role: str  # user or assistant or system
    content: str  # 内容
    def __init__(self):
        self.role = "user"  # user or assistant
        self.content = ""


class ChatConfig:
    compose_id: int  # 模型ID
    auth_tag: str  # 身份标识
    deep_search: int  # 深度思考
    internet_search: int  # 网络搜索
    def __init__(self):
        self.compose_id = 73
        self.auth_tag = "本科生"
        self.deep_search = 1  # 深度思考
        self.internet_search = 1  # 网络搜索


def history_to_form_data(history:Iterable[ChatSession]) -> dict[str, str]:
    form_data = {}
    offset = 0

    for i, chat_session in enumerate(history):
        if chat_session.role == "system":
            form_data[f"history[{i + offset}][role]"] = "user"
            form_data[f"history[{i + offset}][content]"] = chat_session.content

            offset += 1
            form_data[f"history[{i + offset}][role]"] = "assistant"
            form_data[f"history[{i + offset}][content]"] = "我知道了"

            continue

        form_data[f"history[{i+offset}][role]"] = chat_session.role
        form_data[f"history[{i+offset}][content]"] = chat_session.content

    return form_data


def make_chat_request(content:str, history, config:ChatConfig) -> dict[str, str | int]:
    form_data:dict[str, str | int] = {}
    form_data["content"] = content
    form_data.update(history_to_form_data(history))
    form_data["compose_id"] = config.compose_id
    form_data["auth_tag"] = config.auth_tag
    form_data["deep_search"] = config.deep_search
    form_data["internet_search"] = config.internet_search

    return form_data


def chat(content:str, history, config) -> Generator[str, None, None]:
    form_data: dict[str, str | int] = make_chat_request(content, history, config)
    # response = requests.post(url, data=form_data, cookies=cookies,verify=False)
    with open("./cookies.json", "r") as f:
        cookies = json.load(f)
    # 流式输出
    response = requests.post(url, data=form_data, cookies=cookies, stream=True, verify=False)  # 防止开了代理没法用

    for line in response.iter_lines():

        if line and isinstance(line, bytes):
            # line.decode('utf-8') - data: {"e":0,"m":"操作成功","d":{"type":"0","answer":"<think>好的","url":"","message_id":"","id":"","recommend_data":[],"source":[],"ext":[]}}
            text = line.decode('utf-8')
            if text.startswith('data: '):
                text: str = text[6:]
                json_data = json.loads(text)

                yield json_data["d"]["answer"]


if __name__ == "__main__":
    for i in chat("如何评价山东大学", [], ChatConfig()):
        print(i, end="")
