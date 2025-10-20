import re
import json
import os
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, expect
import requests
from datetime import datetime

# 配置变量（优先读取环境变量，不存在则使用默认值）
NVPW = os.getenv("NVPW", "xxx@koyeb.nyc.mn xxxx")  # 格式: 账号 密码
NVURL = os.getenv("NVURL", "")
COOKIES_FILE = os.getenv("COOKIES_FILE", "nvidia_cookies.json")
TG_CONFIG = os.getenv("TG", "")  # 格式: ID  TOKEN


def save_cookies(context, filename=COOKIES_FILE) -> None:
    """保存cookie到文件"""
    cookies = context.cookies()
    with open(filename, 'w') as f:
        json.dump(cookies, f, indent=2)
    print(f"Cookie已保存到 {filename}")


def load_cookies(context, filename=COOKIES_FILE) -> bool:
    """从文件加载cookie"""
    if not Path(filename).exists():
        print(f"Cookie文件不存在")
        return False
    
    try:
        with open(filename, 'r') as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"Cookie已从 {filename} 加载")
        return True
    except Exception as e:
        print(f"加载Cookie失败: {e}")
        return False


def login_with_password(page, email, password) -> bool:
    """使用密码登陆"""
    try:
        page.goto("https://air.nvidia.com/login")
        page.get_by_placeholder("Business Email Address").click()
        page.get_by_placeholder("Business Email Address").fill(email)
        page.get_by_role("button", name="Next").click()
        page.wait_for_timeout(1000)
        
        page.get_by_placeholder("Enter your password").click()
        page.get_by_placeholder("Enter your password").fill(password)
        page.get_by_role("button", name="Log In").click()
        page.wait_for_timeout(30000)  # 等待30秒
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # 检查是否登陆成功（跳转到simulations页面）
        if "simulations" in page.url:
            print("密码登陆成功")
            return True
        else:
            print("密码登陆失败")
            return False
    except Exception as e:
        print(f"密码登陆错误: {e}")
        return False


def try_cookie_login(page) -> bool:
    """尝试使用cookie登陆"""
    try:
        page.goto(NVURL)
        page.wait_for_timeout(20000)  # 等待20秒
        
        # 检查是否成功访问（如果被重定向到登陆页面则失败）
        if "login" in page.url or page.url == "https://air.nvidia.com/":
            print("Cookie登陆失败，需要重新登陆")
            return False
        else:
            print("登陆成功")
            return True
    except Exception as e:
        print(f"Cookie登陆错误: {e}")
        return False


def run(playwright: Playwright) -> None:
    # 解析账号和密码
    credentials = NVPW.split(" ", 1)
    email = credentials[0]
    password = credentials[1]
    
    browser = playwright.firefox.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    # 尝试使用cookie登陆
    cookie_loaded = load_cookies(context)
    
    if cookie_loaded and try_cookie_login(page):
        # Cookie登陆成功
        login_success = True
    else:
        # Cookie登陆失败或不存在，使用密码登陆
        page = context.new_page()  # 创建新页面清除状态
        if login_with_password(page, email, password):
            login_success = True
            # 访问simulations确认登陆
            page.goto("https://air.nvidia.com/simulations")
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # 判断并点击"Accept All"按钮（如果存在）
            accept_button = page.get_by_role("button", name="Accept All")
            if accept_button.is_visible():
                accept_button.click()
            
            # 判断并点击"close"按钮（如果存在）
            close_button = page.get_by_role("button", name="close")
            if close_button.is_visible():
                close_button.click()
            
            # 保存cookie
            save_cookies(context)
        else:
            login_success = False
    
    if not login_success:
        print("登陆失败，程序退出")
        page.close()
        context.close()
        browser.close()
        return
    
    # 访问指定模拟URL
    page.goto(NVURL)
    page.wait_for_load_state("networkidle", timeout=10000)
    
    # 循环执行添加时间，最多尝试6次
    max_attempts = 6
    attempts = 0
    
    while attempts < max_attempts:
        try:
            # 检查页面中是否已存在"6 days 23 hours 59 minutes"
            target_text = page.get_by_text("6 days 23 hours 59 minutes", exact=True)
            if target_text.count() > 0:
                print("时间已增加到 6 days 23 hours 59 minutes")
                break
            
            # 点击选项菜单
            page.locator("app-sim-timer app-options-menu").get_by_role("img").click()
            page.wait_for_timeout(500)  # 等待菜单显示
            
            # 点击"Add Time"
            page.get_by_text("Add Time").click()
            page.wait_for_timeout(1000)  # 等待处理
            
            attempts += 1
            print(f"第 {attempts} 次添加时间...")
            
        except Exception as e:
            print(f"错误: {e}")
            attempts += 1
    
    if attempts >= max_attempts:
        print(f"已尝试 {max_attempts} 次，停止增加时间")
    
    page.close()
    context.close()
    browser.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
