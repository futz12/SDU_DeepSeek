from requests import Session
from datetime import datetime, timezone
from re import search


def login(sduid: str, password: str):
    service = "https://aiassist.sdu.edu.cn/common/actionCasLogin?redirect_url=https%3A%2F%2Faiassist.sdu.edu.cn%2Fpage%2Fsite%2FnewPc%3Flogin_return%3Dtrue"
    ss = Session()  # use session to keep cookies
    lt = ss.post(
        "https://pass.sdu.edu.cn/cas/restlet/tickets",
        data=f"username={sduid}&password={password}",
    ).text
    st = ss.post(  # get service ticket
        f"https://pass.sdu.edu.cn/cas/restlet/tickets/{lt}",
        data=f"service={service}",
    ).text
    if not st.startswith("ST-"):
        raise ValueError("Login failed, please check your credentials.")
    ss.get(f"{service}&ticket={st}", allow_redirects=True)  # get cookies
    data = ss.get("https://aiassist.sdu.edu.cn/site/user_info")  # get expiration time
    print(f"Welcome {data.json()["d"]["user_name"]}!")
    return {
        "cookies": {k: v for k, v in ss.cookies.items()},
        "expires": datetime.strptime(
            search(r"expires=([^;]+)", data.headers["Set-Cookie"]).group(1),
            "%a, %d-%b-%Y %H:%M:%S GMT",
        ).replace(tzinfo=timezone.utc),
    }


if __name__ == "__main__":
    from getpass import getpass

    sduid = input("SDU ID: ")
    password = getpass("Password: ")
    print(login(sduid, password))
