from datetime import datetime


def log(message):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{timestamp}] {message}"

    print(line)

    with open("logs/system.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")