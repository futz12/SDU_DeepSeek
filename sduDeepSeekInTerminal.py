import requests, os, toml, json
from rich.console import Console
from rich.markdown import Markdown
from datetime import datetime, timezone
from getpass import getpass
from sdu_aiassist_login import login

if os.path.exists("SDUTAIconfigs.toml"):
    with open("SDUTAIconfigs.toml", "r") as f:
        configs = toml.load(f)
        f.close()
    if configs["expires"] > datetime.now(timezone.utc):
        cookies = configs["cookies"]
    else:
        exit(print("Cookie expired, please delete SDUTAIconfigs.toml"))
else:
    sduid = input("SDU ID: ")
    password = getpass("Password: ")
    configs = login(sduid, password)
    configs["online"] = False
    configs["reason"] = True
    cookies = configs["cookies"]

commands = {"exit": {"message": "Goodbye!", "exec": ""},
            "clear": {"message": "History cleared.",
                      "exec": """history = []"""},
            "online": {"message": "Internet search enabled.",
                       "exec": """configs["online"] = True"""},
            "offline": {"message": "Internet search disabled.",
                        "exec": """configs["online"] = False"""},
            "r1": {"message": "Model switched to deepseek-r1.",
                   "exec": """configs["reason"] = True"""},
            "v3": {"message": "Model switched to deepseek-v3.",
                   "exec": """configs["reason"] = False"""},
            "help": {
                "message": "usage\n\t:command\ncommands\n\texit, clear, online, offline, r1, v3, help",
                "exec": ""}}
print("SDU DeepSeek in Terminal\nType :help for a list of commands.")
history = []

while True:
    content = input(">_ ")
    if content == "":
        content = ":"
    if content.startswith(":"):
        cmd = content[1:]
        if cmd in commands:
            print(commands[cmd]["message"])
            if cmd == "exit":
                break
            exec(commands[cmd]["exec"])
        else:
            print("Invalid command. Type :help for a list of commands.")
        continue
    form_data = {
        "compose_id": 73, "auth_tag": "本科生", "content": content,
        "deep_search": 1 if configs["reason"] else 2,
        "internet_search": 1 if configs["online"] else 2}
    for i, chat_session in enumerate(history):
        form_data[f"history[{i}][role]"] = chat_session["role"]
        form_data[f"history[{i}][content]"] = chat_session["content"]
    time_start = datetime.now()
    response = requests.post(
        "https://aiassist.sdu.edu.cn/site/ai/compose_chat",
        data=form_data, cookies=cookies, stream=True)
    answer = ""
    for line in response.iter_lines():
        if line:
            text = line.decode("utf-8")
            if text.startswith("data: "):
                text = text[6:]
                json_data = json.loads(text)
                answer += json_data["d"]["answer"]
                print(json_data["d"]["answer"], end="")
    time_delta = datetime.now() - time_start
    history.append({"role": "user", "content": content})
    history.append({"role": "assistant", "content": answer})
    print(f"\n\nGenerated in {time_delta.total_seconds():.2f} seconds")
    console = Console(width=80)
    if configs["reason"]:
        answer = answer[answer.find("</think>") + 10:]
    if "\n" in answer:
        console.print(Markdown(answer))

with open("SDUTAIconfigs.toml", "w") as f:
    toml.dump(configs, f)
    f.close()
