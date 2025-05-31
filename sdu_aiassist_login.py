import re, hashlib, json, httpx, uuid
from uniform_login_des import strEnc
from datetime import datetime, timezone


class VerificationCodeRequiredException(Exception):
    """当需要验证码时抛出的异常"""
    def __init__(self, message: str, login_state: dict):
        super().__init__(message)
        self.login_state = login_state


def attempt_login_without_code(sduid: str, password: str,
                  fingerprint: str | None = str(uuid.uuid4())):
    page = httpx.get(
        "https://pass.sdu.edu.cn/cas/login",
        params={
            "service": "https://aiassist.sdu.edu.cn/common/actionCasLogin?redirect_url=https%3A%2F%2Faiassist.sdu.edu.cn%2Fpage%2Fsite%2FnewPc%3Flogin_return%3Dtrue"})
    lt = re.findall(r'"lt" value="(.*?)"', page.text)[0]
    rsa = strEnc(sduid + password + lt, "1", "2", "3")
    execution = re.findall('"execution" value="(.*?)"', page.text)[0]
    event_id = re.findall('"_eventId" value="(.*?)"', page.text)[0]
    murmur_s = hashlib.sha256(fingerprint.encode()).hexdigest() # type: ignore
    device_status = httpx.post(
        "https://pass.sdu.edu.cn/cas/device",
        data={
            "u": strEnc(sduid, "1", "2", "3"),
            "p": strEnc(password, "1", "2", "3"),
            "m": "1",
            "d": fingerprint, "d_s": murmur_s,
            "d_md5": hashlib.md5(murmur_s.encode()).hexdigest(),
        }, cookies=page.cookies)
    device_status_dict = json.loads(device_status.text)
    match device_status_dict.get("info"):
        case "binded" | "pass":
            # 直接登录
            return _finish_login(page, sduid, password, fingerprint, rsa, lt, execution, event_id)
        case "bind":
            tmp = httpx.post(
                "https://pass.sdu.edu.cn/cas/device",
                data={"m": "2"}, cookies=page.cookies)
            if tmp.text == '{"info":"send"}':
                # 已发送验证码，抛出异常，交由外部处理验证码输入
                raise VerificationCodeRequiredException(
                    "SMS verification code required.",
                    {
                        "page_cookies": page.cookies,
                        "fingerprint": fingerprint,
                        "murmur_s": murmur_s,
                        "sduid": sduid,
                        "rsa": rsa,
                        "lt": lt,
                        "execution": execution,
                        "event_id": event_id
                    }
                )
            else:
                raise SystemError(f"Unknown SMS status: {tmp.text}")
        case _:
            print(
                "Please check your username. Device information cannot be loaded by SDU pass.")
            raise SystemError(
                "Unknown device status: {}".format(str(device_status_dict)))

def continue_login_with_code(login_state: dict, code: str, remember_device: bool = False):
    # login_state: 由 VerificationCodeRequiredException.login_state 提供
    page_cookies = login_state["page_cookies"]
    fingerprint = login_state["fingerprint"]
    murmur_s = login_state["murmur_s"]
    sduid = login_state["sduid"]
    rsa = login_state["rsa"]
    lt = login_state["lt"]
    execution = login_state["execution"]
    event_id = login_state["event_id"]
    body = {
        "d": murmur_s, "i": fingerprint, "m": "3", "u": sduid,
        "c": code, "s": "1" if remember_device else "0"
    }
    k = httpx.post("https://pass.sdu.edu.cn/cas/device",
                   data=body, cookies=page_cookies)
    while k.text == '{"info":"codeErr"}':
        raise ValueError("Verification code error.")
    if k.text == '{"info":"ok"}' or k.text == '{"info":"most"}':
        # 验证码通过，继续登录
        return _finish_login_with_state(page_cookies, sduid, fingerprint, rsa, lt, execution, event_id)
    else:
        raise SystemError(f"Unknown response after code submit: {k.text}")

def _finish_login(page, sduid, password, fingerprint, rsa, lt, execution, event_id):
    page = httpx.post(
        "https://pass.sdu.edu.cn/cas/login", cookies=page.cookies, params={
            "service": "https://aiassist.sdu.edu.cn/common/actionCasLogin?redirect_url=https%3A%2F%2Faiassist.sdu.edu.cn%2Fpage%2Fsite%2FnewPc%3Flogin_return%3Dtrue"},
        data={"rsa": rsa, "ul": len(sduid), "pl": len(password), "lt": lt,
              "execution": execution, "_eventId": event_id})
    page = httpx.get(page.headers["location"])
    return {
        "cookies": {cookie: value for cookie, value in page.cookies.items()},
    }

def _finish_login_with_state(page_cookies, sduid, fingerprint, rsa, lt, execution, event_id):
    page = httpx.post(
        "https://pass.sdu.edu.cn/cas/login", cookies=page_cookies, params={
            "service": "https://aiassist.sdu.edu.cn/common/actionCasLogin?redirect_url=https%3A%2F%2Faiassist.sdu.edu.cn%2Fpage%2Fsite%2FnewPc%3Flogin_return%3Dtrue"},
        data={"rsa": rsa, "ul": len(sduid), "pl": len(fingerprint), "lt": lt,
              "execution": execution, "_eventId": event_id})
    return {
        "cookies": {cookie: value for cookie, value in page.cookies.items()},
    }
