#!/usr/bin/env python3
import json
import uuid
import sdu_aiassist_login as login
import time

print("Please confirm that you have successfully logged in and then leave this program running.")
print("It will automatically refresh the cookies every 6 hours.")
print("Press Ctrl+C to exit.")

while True:
    try:
        # 从CSV文件读取用户信息
        with open("./userinfo.csv", "r", encoding="utf-8") as f:
            a = f.read().strip().split(",")
        sdu_id = a[0].strip()
        password = a[1]
        
        if not sdu_id or not password:
            print("用户凭据为空，退出程序")
            exit(1)
        
        # 读取设备指纹
        try:
            with open("./fingerprint.txt", "r") as f:
                fingerprint = f.read().strip()
        except FileNotFoundError:
            fingerprint = str(uuid.uuid4())
            with open("./fingerprint.txt", "w") as f:
                f.write(fingerprint)
            print(f"生成新的设备指纹: {fingerprint}")
        
        # 尝试登录
        try:
            login_result = login.attempt_login_without_code(sdu_id, password, fingerprint)
            cookies = login_result["cookies"]
        except login.VerificationCodeRequiredException as e:
            print("需要验证码，请在api端输入验证码")
            time.sleep(20 * 60)
            continue
        except Exception as e:
            print(f"登录失败: {e}")
            print("等待5分钟后重试...")
            time.sleep(5 * 60)
            continue
        
        if not cookies:
            print("登录失败，cookies为空")
            print("等待5分钟后重试...")
            time.sleep(5 * 60)
            continue
        
        # 保存cookies
        with open("./cookies.json", "w") as f:
            json.dump(cookies, f)
        
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{current_time}] 登录成功，cookies已刷新并保存到 ./cookies.json")
        
        # 等待6小时后再次刷新
        time.sleep(6 * 60 * 60)
        
    except KeyboardInterrupt:
        print("\n程序已停止")
        break
    except Exception as e:
        print(f"发生错误: {e}")
        print("等待5分钟后重试...")
        time.sleep(5 * 60)
