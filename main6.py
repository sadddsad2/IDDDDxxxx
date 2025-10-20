import re
import json
import os
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, expect
import requests
from datetime import datetime

# 配置变量（优先读取环境变量，不存在则使用默认值）
NVPW = os.getenv("NVPW", "xxx@ny.com xxxx")  # 格式: 账号 密码
NVURL = os.getenv("NVURL", "https://air.nvidia.com/simulations/xxfcxxf-d3xx-4x1a-9ce1-233exxxfdfxx")
COOKIES_FILE = os.getenv("COOKIES_FILE", "nvidia_cookies.json")
TG_CONFIG = os.getenv("TG", "")  # 格式: ID TOKEN (一个空格)


def send_tg_notification(message: str) -> None:
    """发送Telegram通知"""
    if not TG_CONFIG:
        print("TG_CONFIG 未设置，跳过发送通知")
        return
    
    if " " not in TG_CONFIG:
        print(f"TG_CONFIG 格式错误，应该是 'ID TOKEN'，当前值: {TG_CONFIG}")
        return
    
    try:
        parts = TG_CONFIG.split(" ", 1)
        chat_id = parts[0].strip()
        token = parts[1].strip()
        
        print(f"准备发送TG通知，Chat ID: {chat_id[:10]}***")
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message
        }
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"? TG通知已发送成功")
        else:
            print(f"? TG通知发送失败: HTTP {response.status_code}")
            print(f"  响应: {response.text}")
    except requests.exceptions.Timeout:
        print(f"? TG通知发送超时（无法连接到api.telegram.org）")
    except requests.exceptions.ConnectionError:
        print(f"? TG通知发送失败（网络连接错误）")
    except Exception as e:
        print(f"? 发送TG通知错误: {e}")


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


def check_time_status(page) -> tuple[bool, str]:
    """
    检查时间状态，返回 (是否达到最大值, 当前时间文本)
    只有达到 6 days 23 hours 59 minutes 才算成功
    使用多种方式检测时间增加是否成功
    """
    try:
        # 等待页面稳定
        page.wait_for_timeout(2000)
        
        # 方式1: 精确匹配目标文本 "6 days 23 hours 59 minutes"
        target_text = "6 days 23 hours 59 minutes"
        try:
            exact_match = page.get_by_text(target_text, exact=True)
            if exact_match.count() > 0:
                print(f"? 方式1检测成功: 找到精确文本 '{target_text}'")
                return True, target_text
        except Exception as e:
            print(f"方式1检测: 未找到精确文本 - {e}")
        
        # 方式2: 模糊匹配 (6 days 23 hours 59)
        try:
            fuzzy_match = page.get_by_text("6 days 23 hours 59")
            if fuzzy_match.count() > 0:
                time_text = fuzzy_match.first.inner_text()
                print(f"? 方式2检测成功: 找到匹配文本 '{time_text}'")
                return True, time_text
        except Exception as e:
            print(f"方式2检测: 未找到匹配文本 - {e}")
        
        # 方式3: 通过定位器查找timer元素
        try:
            timer_element = page.locator("app-sim-timer")
            if timer_element.count() > 0:
                timer_text = timer_element.inner_text()
                print(f"? 方式3检测: Timer元素内容 '{timer_text}'")
                # 必须是 6 days 23 hours 59 minutes
                if "6 days" in timer_text and "23 hours" in timer_text and "59" in timer_text:
                    return True, timer_text
        except Exception as e:
            print(f"方式3检测: 未找到timer元素 - {e}")
        
        # 方式4: 正则表达式匹配页面中的时间文本
        try:
            page_content = page.content()
            pattern = r'(\d+)\s*days?\s*(\d+)\s*hours?\s*(\d+)\s*minutes?'
            matches = re.findall(pattern, page_content, re.IGNORECASE)
            if matches:
                for match in matches:
                    days, hours, minutes = match
                    time_str = f"{days} days {hours} hours {minutes} minutes"
                    print(f"? 方式4检测: 找到时间文本 '{time_str}'")
                    # 必须是 6 天 23 小时 59 分钟
                    if int(days) == 6 and int(hours) == 23 and int(minutes) == 59:
                        return True, time_str
        except Exception as e:
            print(f"方式4检测: 正则匹配失败 - {e}")
        
        # 如果所有方式都未检测到最大时间，尝试获取当前时间
        try:
            timer_element = page.locator("app-sim-timer")
            if timer_element.count() > 0:
                current_time = timer_element.inner_text().strip()
                print(f"当前时间: {current_time}")
                return False, current_time
        except:
            pass
        
        # 所有方式都未检测到
        print("? 未检测到最大时间 (6 days 23 hours 59 minutes)")
        return False, "未检测到"
        
    except Exception as e:
        print(f"检查时间状态错误: {e}")
        return False, "检查失败"


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
            try:
                accept_button = page.get_by_role("button", name="Accept All")
                if accept_button.is_visible():
                    accept_button.click()
            except:
                pass
            
            # 判断并点击"close"按钮（如果存在）
            try:
                close_button = page.get_by_role("button", name="close")
                if close_button.is_visible():
                    close_button.click()
            except:
                pass
            
            # 保存cookie
            save_cookies(context)
        else:
            login_success = False
    
    if not login_success:
        print("登陆失败，程序退出")
        send_tg_notification(f"? NVIDIA Air 登陆失败\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        page.close()
        context.close()
        browser.close()
        return
    
    # 访问指定模拟URL
    page.goto(NVURL)
    page.wait_for_load_state("networkidle", timeout=10000)
    
    # 检查初始时间状态
    print("\n=== 检查初始时间状态 ===")
    initial_success, initial_time = check_time_status(page)
    print(f"初始时间: {initial_time}")
    
    if initial_success:
        print(f"? 初始检测: 时间已经是最大值 (6 days 23 hours 59 minutes)")
        send_tg_notification(
            f"? NVIDIA Air 登陆成功\n"
            f"时间状态: 已是最大值\n"
            f"初始时间: {initial_time}\n"
            f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        page.close()
        context.close()
        browser.close()
        return
    
    print(f"初始时间未达到最大值，需要增加时间")
    
    # 循环执行添加时间，最多尝试6次
    max_attempts = 6
    attempts = 0
    time_added = False
    final_time = initial_time  # 记录最终时间
    
    print(f"\n=== 开始尝试增加时间（最多{max_attempts}次）===")
    
    while attempts < max_attempts:
        try:
            # 点击选项菜单
            page.locator("app-sim-timer app-options-menu").get_by_role("img").click()
            page.wait_for_timeout(500)  # 等待菜单显示
            
            # 点击"Add Time"
            page.get_by_text("Add Time").click()
            page.wait_for_timeout(2000)  # 等待处理
            
            attempts += 1
            print(f"? 第 {attempts} 次添加时间操作完成")
            
            # 每次点击后检查时间状态
            success, current_time = check_time_status(page)
            final_time = current_time  # 更新最终时间
            
            if success:
                print(f"? 第 {attempts} 次尝试后检测: 时间已增加到最大值 ({current_time})")
                time_added = True
                break
            else:
                print(f"第 {attempts} 次尝试后: 当前时间 {current_time}，继续尝试...")
            
        except Exception as e:
            print(f"? 第 {attempts + 1} 次尝试出错: {e}")
            attempts += 1
    
    # 达到最大尝试次数后，最后再检查一次
    if not time_added:
        print(f"\n=== 已达到最大尝试次数 ({max_attempts})，最后检查时间状态 ===")
        page.wait_for_timeout(3000)  # 多等待一会儿
        final_success, final_time = check_time_status(page)
        
        if final_success:
            print(f"? 最终检测成功: 时间已增加到最大值 ({final_time})")
            time_added = True
        else:
            print(f"? 最终检测: 时间未达到最大值 ({final_time})")
    
    # 发送通知（无论成功失败都发送）
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if time_added:
        notification_message = (
            f"✅ NVIDIA Air 时间增加成功\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"初始时间: {initial_time}\n"
            f"增加后时间: {final_time}\n"
            f"尝试次数: {attempts}/{max_attempts}\n"
            f"执行时间: {current_datetime}"
        )
        print(f"\n{notification_message}")
        send_tg_notification(notification_message)
    else:
        notification_message = (
            f"✅ NVIDIA Air 时间未达到最大值\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"初始时间: {initial_time}\n"
            f"当前时间: {final_time}\n"
            f"尝试次数: {attempts}/{max_attempts}\n"
            f"建议: 请手动登录检查\n"
            f"执行时间: {current_datetime}"
        )
        print(f"\n{notification_message}")
        send_tg_notification(notification_message)
    
    page.close()
    context.close()
    browser.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
