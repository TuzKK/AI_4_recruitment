"""
使用系统默认浏览器打开BOSS直聘
"""
import webbrowser
import sys
from pathlib import Path
import os

def open_boss_zhipin():
    print("尝试使用系统默认浏览器打开BOSS直聘...")

    # 尝试多个BOSS直聘的可能URL
    urls = [
        "https://www.zhipin.com/",
        "https://www.zhipin.com/web/geek/job",
        "https://login.zhipin.com/"
    ]

    for url in urls:
        print(f"打开: {url}")
        success = webbrowser.open(url)
        if success:
            print("浏览器已启动")
            break
        else:
            print(f"无法使用默认浏览器打开 {url}")

    print("\n请检查浏览器是否已打开，并手动完成登录步骤")
    print("完成登录后，请返回到这里继续操作")


if __name__ == "__main__":
    open_boss_zhipin()