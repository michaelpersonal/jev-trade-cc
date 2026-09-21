"""Jev 只知道你告诉她的 —— 一个五分钟就能跑完的实验。

    pip install typesafe-sdk
    export TYPESAFE_API_KEY=...
    python what_day_is_it.py

总成本约 0.00005 美元。
"""
import os

from typesafe_sdk import TypeSafeClient, Choice, Noul

client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
MODEL = "jev-1.13.0"
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday")

# 同一个问题，两套选项：一套逼她必须挑一天，一套允许她说"说不出来"。
FORCED = Choice(instructions="What day of the week is it today?",
                criteria={d: f"Today is {d}." for d in DAYS})
WITH_EXIT = Choice(instructions="What day of the week is it today?",
                   criteria={**{d: f"Today is {d}." for d in DAYS},
                             "cannot_tell": "Nothing in the text says what day "
                                            "it is, and it cannot be worked out "
                                            "from what is given."})


def run(title, state, questions):
    print(f"\n--- {title}")
    print(f"    state: {state!r}")
    for name, a in client.system_one(state=state, questions=questions,
                                     model=MODEL).answers.items():
        if getattr(a, "noul", None) is not None:
            print(f"    {name:<11} {a.noul:.2f}")
        else:
            top = sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:3]
            print(f"    {name:<11} {a.choice}  (confidence {a.confidence:.2f}, "
                  f"七选一的基线是 0.14)")
            print(f"    {'':<11} " + "  ".join(f"{k} {v:.2f}" for k, v in top))


run("1  没有背景，也没有退路：她只能硬选一个", " ", {"weekday": FORCED})
run("2  同样没有背景，但给了她一个诚实的选项", " ", {"weekday": WITH_EXIT})
run("3  把答案放进背景里", "It is Thursday afternoon.", {"weekday": WITH_EXIT})
run("4  只要背景里写了，她就照单全收", "Today is Monday.",
    {"is_monday": Noul(instructions="Is today Monday?")})
run("4b 背景里换一天，她也照单全收", "Today is Friday.",
    {"is_monday": Noul(instructions="Is today Monday?")})
run("5  背景自相矛盾时，概率会分给两边",
    "Today is Monday. Today is Friday.", {"weekday": FORCED})

print("\n--- 6  同一个请求连问六次：注意她并不是确定性的")
print("    ", end="")
for _ in range(6):
    a = client.system_one(state=" ", questions={"w": FORCED},
                          model=MODEL).answers["w"]
    print(f"{a.choice[:3]}/{a.confidence:.2f} ", end="", flush=True)
print("\n    置信度贴近基线时，连赢家本身都是不稳定的。")
