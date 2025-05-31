import xml
import xml.dom
import xml.dom.minidom
from fastapi import FastAPI
import sduwrap
from sduwrap import ChatConfig, ChatSession

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import uuid
import time
import csv
import os
from typing import Generator, Iterable
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any

# 导入登录相关模块
from sdu_aiassist_login import *

app = FastAPI(
    title="SDU DeepSeek Chat API",
    description="""
    ## SDU DeepSeek 聊天 API 服务
    
    这是一个与 OpenAI ChatGPT API 兼容的聊天服务，基于山东大学AI助手平台构建。
    
    ### 支持的模型
    
    | 模型名称 | 描述 | 特性 |
    |---------|------|------|
    | `deepseek_reasoner_web` | DeepSeek 推理模型（网络版） | 支持推理链，可访问网络 |
    | `deepseek_reasoner` | DeepSeek 推理模型 | 支持推理链 |
    | `deepseek_web` | DeepSeek 标准模型（网络版） | 可访问网络 |
    | `deepseek` | DeepSeek 标准模型 | 基础对话模型 |
    | `QwQ` | QwQ 标准模型 | 基础对话模型 |
    | `QwQ_web` | QwQ 模型（网络版） | 可访问网络 |
    | `QwQ_reasoner` | QwQ 推理模型 | 支持推理链 |
    | `QwQ_reasoner_web` | QwQ 推理模型（网络版） | 支持推理链，可访问网络 |
    
    ### 功能特点
    
    - 🤖 **多模型支持**: 支持 DeepSeek 和 QwQ 系列模型
    - 🌐 **网络搜索**: 部分模型支持实时网络搜索
    - 🧠 **推理链**: 某些模型提供推理过程展示
    - ⚡ **流式响应**: 支持实时流式输出
    - 🔄 **对话历史**: 完整的多轮对话支持
    - 🔌 **API 兼容**: 与 OpenAI ChatGPT API 完全兼容
    
    ### 使用方法
    
    发送 POST 请求到 `/v1/chat/completions` 端点，格式与 OpenAI API 相同。
    """,
    version="1.0.0",
    contact={
        "name": "SDU DeepSeek API",
        "url": "https://github.com/yourusername/SDU_DeepSeek",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 根据需求调整允许的源
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],  # 明确允许 OPTIONS 和 POST
    allow_headers=["*"],  # 允许所有头
)


# Pydantic 模型定义
class Message(BaseModel):
    """聊天消息模型"""

    role: str = Field(..., description="消息角色，支持 'user', 'assistant', 'system'")
    content: str = Field(..., description="消息内容")


class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""

    messages: List[Message] = Field(..., description="对话消息列表")
    model: str = Field(
        default="deepseek_reasoner_web",
        description="模型名称，支持: deepseek_reasoner_web, deepseek_reasoner, deepseek_web, deepseek, QwQ, QwQ_web, QwQ_reasoner, QwQ_reasoner_web",
    )
    stream: bool = Field(default=False, description="是否启用流式响应")
    max_tokens: Optional[int] = Field(default=None, description="最大生成token数")
    temperature: Optional[float] = Field(default=None, description="采样温度")


class ChatCompletionChoice(BaseModel):
    """聊天完成选择项"""

    index: int = Field(..., description="选择项索引")
    message: Message = Field(..., description="生成的消息")
    finish_reason: str = Field(..., description="完成原因")


class ChatCompletionUsage(BaseModel):
    """聊天完成使用统计"""

    prompt_tokens: int = Field(..., description="提示词token数")
    completion_tokens: int = Field(..., description="完成token数")
    total_tokens: int = Field(..., description="总token数")


class ChatCompletionResponse(BaseModel):
    """聊天完成响应模型"""

    id: str = Field(..., description="响应ID")
    object: str = Field(..., description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="使用的模型")
    choices: List[ChatCompletionChoice] = Field(..., description="生成的选择项列表")
    usage: ChatCompletionUsage = Field(..., description="使用统计")


class StreamChoice(BaseModel):
    """流式响应选择项"""

    index: int = Field(..., description="选择项索引")
    delta: Dict[str, Any] = Field(..., description="增量内容")
    finish_reason: Optional[str] = Field(default=None, description="完成原因")


class StreamResponse(BaseModel):
    """流式响应模型"""

    id: str = Field(..., description="响应ID")
    object: str = Field(..., description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="使用的模型")
    choices: List[StreamChoice] = Field(..., description="流式选择项列表")


class ModelInfo(BaseModel):
    """模型信息"""

    id: str = Field(..., description="模型ID")
    object: str = Field(default="model", description="对象类型")
    features: Dict[str, bool] = Field(..., description="模型特性")


class ModelListResponse(BaseModel):
    """模型列表响应"""

    object: str = Field(default="list", description="对象类型")
    data: List[ModelInfo] = Field(..., description="模型列表")


# 登录相关的Pydantic模型
class LoginRequest(BaseModel):
    """用户登录请求模型"""

    sdu_id: str = Field(..., description="山东大学学号", min_length=1)
    password: str = Field(..., description="密码", min_length=1)
    fingerprint: Optional[str] = Field(
        default=None, description="设备指纹，为空则自动生成"
    )
    save_credentials: bool = Field(
        default=True, description="是否保存账户信息到userinfo.csv"
    )


class LoginResponse(BaseModel):
    """用户登录响应模型"""

    success: bool = Field(..., description="登录是否成功")
    message: str = Field(..., description="登录结果消息")
    fingerprint: Optional[str] = Field(default=None, description="设备指纹")


class LoginStatusResponse(BaseModel):
    """登录状态响应模型"""

    is_logged_in: bool = Field(..., description="是否已登录")
    last_login: Optional[int] = Field(default=None, description="最后登录时间戳")
    details: Optional[str] = Field(default=None, description="登录状态详情")


class UserInfo(BaseModel):
    """用户信息模型"""

    sdu_id: str = Field(..., description="山东大学学号")
    last_login: Optional[int] = Field(default=None, description="最后登录时间戳")
    name: Optional[str] = Field(default=None, description="姓名")
    fingerprint: Optional[str] = Field(..., description="设备指纹")


class UserListResponse(BaseModel):
    """用户列表响应模型"""

    users: List[UserInfo] = Field(..., description="用户列表")
    total: int = Field(..., description="用户总数")


class RefreshResponse(BaseModel):
    """刷新响应模型"""

    success: bool = Field(..., description="刷新是否成功")
    message: str = Field(..., description="刷新结果消息")
    expires_at: Optional[int] = Field(default=None, description="新的过期时间戳")


# 全局变量存储登录状态
login_state = None
login_time = None
other_recs = None


def save_user_to_csv(sdu_id: str, password: str, fingerprint: str):
    """保存用户信息到CSV文件"""
    # 读取现有用户信息
    csv_file = "./userinfo.csv"

    def login(username, password, baseURL="https://pass.sdu.edu.cn/") -> str:
        # 发送第一个请求，获取ticket
        ticket = httpx.post(
            f"{baseURL}cas/restlet/tickets",
            data={"username": username, "password": password},
        ).text
        # print("ticket: " + ticket)
        # 检查ticket是否以TGT开头
        if not ticket.startswith("TGT"):
            raise Exception(
                "ticket should start with TGT. Check your username and password."
            )

        # 发送第二个请求，获取sTicket
        sTicket = httpx.post(
            f"{baseURL}cas/restlet/tickets/{ticket}",
            content="service=https://service.sdu.edu.cn/tp_up/view?m=up",
            headers={"Content-Type": "text/plain"},
        ).text
        # print("sTicket: " + sTicket)
        # 检查sTicket是否以ST开头
        if not sTicket.startswith("ST"):
            raise Exception("sTicket should start with ST")

        return sTicket

    def get_user_name_and_id(sTicket, baseURL="https://pass.sdu.edu.cn/"):
        user_data = xml.dom.minidom.parseString(
            httpx.get(
                f"{baseURL}cas/serviceValidate",
                params={
                    "ticket": sTicket,
                    "service": "https://service.sdu.edu.cn/tp_up/view?m=up",
                },
            ).text
        )
        name = user_data.getElementsByTagName("cas:USER_NAME")[0].childNodes[0].data  # type:ignore
        student_id = user_data.getElementsByTagName("sso:user")[0].childNodes[0].data # type:ignore
        return name, student_id

    name, _ = get_user_name_and_id(login(sdu_id, password))
    user = [sdu_id, password, name, fingerprint, int(time.time())]

    # 写回文件
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(user)


def get_user_from_csv() -> UserInfo:
    """从CSV文件获取用户列表"""

    csv_file = "./userinfo.csv"
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"User info file {csv_file} does not exist.")
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            line = next(reader, None)
            assert line is not None, "User info file is empty."
            assert len(line) >= 4, "User info file format is incorrect."
            return UserInfo(
                sdu_id=line[0],
                name=line[2],
                last_login=int(line[4]) if len(line) > 4 else None,
                fingerprint=line[3] if len(line) > 3 else str(uuid.uuid4()),
            )

    except Exception as e:
        raise RuntimeError(f"Failed to read user info from {csv_file}: {str(e)}")


def get_user_credentials(sdu_id: str) -> None | Dict[str, str]:
    """获取用户的登录凭据"""
    csv_file = "./userinfo.csv"

    if not os.path.exists(csv_file):
        return None

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[0] == sdu_id:
                    return {"sdu_id": row[0], "password": row[1]}
    except Exception:
        pass

    return None


def save_cookies(cookies_dict: dict):
    """保存cookies到文件"""
    cookies_file = "./cookies.json"

    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(cookies_dict, f, ensure_ascii=False, indent=2)


def load_cookies(user_uuid: Optional[str] = None):
    """从文件加载cookies"""
    cookies_file = "./cookies.json"
    if user_uuid:
        cookies_file = f"./cookies_{user_uuid}.json"

    if not os.path.exists(cookies_file):
        return None

    try:
        with open(cookies_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def chat(content: str, history: list, config: ChatConfig) -> Generator[str, None, None]:
    """
    聊天函数，用于与 SDU AI 助手进行对话

    Args:
        content: 用户输入内容
        history: 历史对话记录
        config: 聊天配置

    Yields:
        str: 生成的响应文本片段
    """
    request_history: list[ChatSession] = []
    for chat_session in history:
        cs = sduwrap.ChatSession()
        cs.role = chat_session["role"]
        cs.content = chat_session["content"]

        request_history.append(cs)

    for response in sduwrap.chat(content, request_history, config):
        yield response


@app.get(
    "/health",
    summary="健康检查",
    description="检查 API 服务健康状态",
    tags=["基础信息"],
)
async def health_check():
    """
    健康检查端点

    Returns:
        dict: 服务健康状态信息
    """
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "service": "SDU DeepSeek Chat API",
    }


model_config = {
    "deepseek_reasoner_web": (73, "本科生", 1, 1),
    "deepseek_reasoner": (73, "本科生", 1, 2),
    "deepseek_web": (73, "本科生", 2, 1),
    "deepseek": (73, "本科生", 2, 2),
    "QwQ": (72, "本科生", 2, 2),
    "QwQ_web": (72, "本科生", 2, 1),
    "QwQ_reasoner": (72, "本科生", 1, 2),
    "QwQ_reasoner_web": (72, "本科生", 1, 1),
}


@app.post(
    "/v1/chat/completions",
    response_model=Union[ChatCompletionResponse, StreamResponse],
    summary="OpenAI 兼容的聊天完成接口",
    description="提供与 OpenAI ChatGPT API 兼容的聊天完成服务，支持多种模型和流式响应",
    response_description="聊天完成响应，包含生成的内容和使用统计",
    tags=["聊天接口"],
)
async def openai_chat_completion(
    request: ChatCompletionRequest,
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """
    OpenAI 兼容的聊天完成接口

    该接口提供与 OpenAI ChatGPT API 兼容的聊天完成服务，支持：
    - 多种模型选择（DeepSeek 和 QwQ 系列）
    - 流式和非流式响应
    - 完整的对话历史支持
    - 搜索功能（根据模型配置）

    Args:
        request: 聊天完成请求，包含消息列表、模型选择等参数

    Returns:
        ChatCompletionResponse: 非流式响应，包含完整的生成内容
        StreamingResponse: 流式响应，实时返回生成内容

    Raises:
        HTTPException: 当请求格式无效或消息格式错误时抛出

    Example:
        ```json
        {
            "messages": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            "model": "deepseek_reasoner_web",
            "stream": false
        }
        ```
    """
    # 提取必要参数
    messages = request.messages
    stream = request.stream
    model = request.model

    config = ChatConfig()

    if model in model_config:
        (
            config.compose_id,
            config.auth_tag,
            config.deep_search,
            config.internet_search,
        ) = model_config[model]

    # 校验消息格式
    if not messages or messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="Invalid messages format: last message must be from user",
        )

    # 提取当前输入和历史记录
    current_input = messages[-1].content
    history = [{"role": msg.role, "content": msg.content} for msg in messages[:-1]]

    # 流式响应处理
    if stream:
        def generate_stream():
            # 生成唯一响应ID
            response_id = f"sdu_ds-{uuid.uuid4()}"
            created = int(time.time())

            # 遍历生成器生成事件流
            for chunk in chat(current_input, history, config):
                event_data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
                    ],
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            # 结束事件
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(), media_type="text/event-stream"
        )  # 非流式响应处理
    else:
        # 收集完整响应
        full_response = "".join(
            [chunk for chunk in chat(current_input, history, config)]
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            object="chat.completion",
            created=int(time.time()),
            model=model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(role="assistant", content=full_response),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=len(current_input),
                completion_tokens=len(full_response),
                total_tokens=len(current_input) + len(full_response),
            ),
        )


@app.get(
    "/v1/models",
    response_model=ModelListResponse,
    summary="获取可用模型列表",
    description="返回所有可用的聊天模型及其特性信息",
    tags=["模型管理"],
)
async def list_models():
    """
    获取可用模型列表

    Returns:
        ModelListResponse: 包含所有可用模型信息的响应
    """
    model_configs = {
        "deepseek_reasoner_web": {"reasoning": True, "web_search": True},
        "deepseek_reasoner": {"reasoning": True, "web_search": False},
        "deepseek_web": {"reasoning": False, "web_search": True},
        "deepseek": {"reasoning": False, "web_search": False},
        "QwQ": {"reasoning": False, "web_search": False},
        "QwQ_web": {"reasoning": False, "web_search": True},
        "QwQ_reasoner": {"reasoning": True, "web_search": False},
        "QwQ_reasoner_web": {"reasoning": True, "web_search": True},
    }

    models = []

    for model_id, features in model_configs.items():
        models.append(ModelInfo(id=model_id, features=features))

    return ModelListResponse(data=models)


@app.post(
    "/v1/auth/login",
    response_model=LoginResponse,
    summary="用户登录",
    description="使用山东大学账号和密码进行登录，获取session cookies",
    tags=["用户认证"],
)
async def login_user(request: LoginRequest) -> LoginResponse:
    """
    用户登录接口

    使用山东大学学号和密码进行登录，系统会：
    1. 验证用户凭据
    2. 生成用户UUID标识
    3. 保存登录状态和cookies
    4. 可选择保存账户信息到userinfo.csv

    Args:
        request: 登录请求，包含学号、密码、设备指纹等信息

    Returns:
        LoginResponse: 登录结果，包含成功状态、用户UUID、设备指纹等

    Raises:
        HTTPException: 当登录失败时抛出

    Example:        ```json
        {
            "sdu_id": "202000123456",
            "password": "your_password",
            "fingerprint": "optional_device_fingerprint",
            "save_credentials": true
        }
        ```
    """
    global login_state, login_time, other_recs

    try:  # 处理设备指纹
        fingerprint = request.fingerprint
        if not fingerprint:
            # 如果没有提供指纹，则生成一个新的UUID作为指纹
            #
            # read existing
            try:
                with open("./fingerprint.txt", "r") as f:
                    fingerprint = f.read()
            except:
                fingerprint = str(uuid.uuid4())

        login_result = attempt_login_without_code(
            request.sdu_id,
            request.password,
            fingerprint,
        )

        if not login_result or not login_result.get("cookies"):
            raise HTTPException(status_code=401, detail="登录失败：用户名或密码错误")

        # 保存全局状态
        current_cookies = login_result["cookies"]
        login_time = int(
            time.time()
        )
        # 保存cookies到文件
        save_cookies(current_cookies)  # 也保存到默认文件，保持兼容性

        # 如果需要保存凭据
        if request.save_credentials:
            with open("./fingerprint.txt", "w", encoding="utf-8") as f:
                f.write(fingerprint)
            save_user_to_csv(request.sdu_id, request.password, fingerprint)

        return LoginResponse(
            success=True,
            message="登录成功",
            fingerprint=fingerprint,
        )

    except VerificationCodeRequiredException as e:
        login_state = e.login_state
        other_recs = {
            "save_credentials": request.save_credentials,
            "sdu_id": request.sdu_id,
            "password": request.password,
            "fingerprint": e.login_state["fingerprint"],
        }
        raise HTTPException(
            status_code=400,
            detail=f"需要验证码: {e.args[0]}。请在300秒内前往验证码api发送验证码。",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录过程中发生错误: {str(e)}")


@app.post(
    "/v1/auth/continue_login",
    response_model=LoginResponse,
    summary="继续登录",
    description="在需要验证码的情况下，使用验证码继续登录",
)
async def continue_login(code: str, rem: bool = False) -> LoginResponse:
    """
    继续登录接口

    在需要验证码的情况下，使用验证码继续登录。

    Args:
        code: 用户输入的验证码

    Returns:
        LoginResponse: 登录结果，包含成功状态、用户UUID、设备指纹等

    Raises:
        HTTPException: 当验证码错误或登录失败时抛出
    """
    global login_state, login_time, other_recs

    if not login_state:
        raise HTTPException(status_code=400, detail="没有进行登录请求或登录状态已过期")

    try:
        # 使用验证码继续登录
        login_result = continue_login_with_code(login_state, code, remember_device=rem)

        if not login_result or not login_result.get("cookies"):
            raise HTTPException(status_code=401, detail="验证码错误或登录失败")

        # 保存全局状态
        current_cookies = login_result["cookies"]

        # 保存cookies到文件
        save_cookies(current_cookies)  # 也保存到默认文件，保持兼容性

        # 保存用户信息到CSV
        if other_recs and other_recs.get("save_credentials", True):
            login_state["sduid"] = other_recs["sdu_id"]
            login_state["password"] = other_recs["password"]
            login_state["fingerprint"] = other_recs["fingerprint"]
            save_user_to_csv(
                login_state["sduid"],
                login_state["password"],
                login_state["fingerprint"],
            )
        # remove those temp things
        fp = login_state["fingerprint"]
        if rem:
            with open("./fingerprint.txt", "w") as f:
                f.write(fp)
        login_state = None
        other_recs = None
        return LoginResponse(
            success=True,
            message="登录成功",
            fingerprint=fp,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"继续登录过程中发生错误: {str(e)}")


@app.get(
    "/v1/auth/status",
    response_model=LoginStatusResponse,
    summary="检查登录状态",
    description="检查当前用户的登录状态和会话信息",
    tags=["用户认证"],
)
async def get_login_status() -> LoginStatusResponse:
    """
    检查登录状态

    Returns:
        LoginStatusResponse: 包含登录状态、用户UUID、过期时间等信息
    """
    if login_state:
        return LoginStatusResponse(
            is_logged_in=False,
        )
    is_logged_in = (
        login_time is not None
        and time.time() - login_time < 24 * 60 * 60
    )
    if is_logged_in:
        try:
            user_info = get_user_from_csv()
            assert user_info
            return LoginStatusResponse(
                is_logged_in=is_logged_in,
                last_login=user_info.last_login,
                details=f"用户 {user_info.sdu_id} {user_info.name}已登录，设备指纹: {user_info.fingerprint}",
            )
        except:
            return LoginStatusResponse(is_logged_in=is_logged_in, last_login=login_time)
    else:
        return LoginStatusResponse(is_logged_in=is_logged_in, last_login=login_time)


@app.post(
    "/v1/auth/refresh",
    response_model=RefreshResponse,
    summary="刷新登录状态",
    description="使用已保存的用户凭据刷新登录状态",
    tags=["用户认证"],
)
async def refresh_login() -> RefreshResponse:
    """
    刷新登录状态

    从userinfo.csv读取保存的用户凭据，重新登录并刷新cookies

    Returns:
        RefreshResponse: 刷新结果和新的过期时间

    Raises:
        HTTPException: 当没有保存的凭据或刷新失败时抛出
    """
    global login_time

    try:
        # 从CSV文件读取用户信息
        csv_file = "./userinfo.csv"
        if not os.path.exists(csv_file):
            raise HTTPException(status_code=404, detail="未找到保存的用户凭据")

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            users = list(reader)

        if not users:
            raise HTTPException(status_code=404, detail="用户凭据文件为空")

        # 使用第一个用户的凭据（兼容auto-ref.py）
        user_row = users[0]
        if len(user_row) < 2:
            raise HTTPException(status_code=400, detail="用户凭据格式错误")

        sdu_id, password = user_row[0], user_row[1]

        # 读取设备指纹
        fingerprint = str(uuid.uuid4())  # 默认值
        try:
            with open("./fingerprint.txt", "r", encoding="utf-8") as f:
                fingerprint = f.read().strip()
        except FileNotFoundError:
            # 生成新的指纹
            with open("./fingerprint.txt", "w", encoding="utf-8") as f:
                f.write(fingerprint)

        login_result = attempt_login_without_code(sdu_id, password, fingerprint)

        if not login_result or not login_result.get("cookies"):
            raise HTTPException(status_code=401, detail="刷新登录失败")

        # 更新全局状态
        current_time = int(time.time())
        login_time = current_time
        current_cookies = login_result["cookies"]

        # 保存新的cookies
        save_cookies(current_cookies)  # 保存到默认文件

        return RefreshResponse(
            success=True,
            message="登录状态刷新成功",
            expires_at=current_time + (24 * 60 * 60),  # 24小时后过期
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新过程中发生错误: {str(e)}")


if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
