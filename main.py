import re
import os
import json
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright, expect, TimeoutError

# Load environment variables from .env file (if it exists)
load_dotenv()

def run(playwright: Playwright) -> None:
    # Get credentials from environment variables - format: "email password"
    google_pw = os.environ.get("GOOGLE_PW", "")
    credentials = google_pw.split(' ', 1) if google_pw else []
    
    email = credentials[0] if len(credentials) > 0 else None
    password = credentials[1] if len(credentials) > 1 else None
    
    app_url = os.environ.get("APP_URL", "https://idx.google.com/app-43646734")
    cookies_path = Path("google_cookies.json")
    
    # Check if credentials are available
    if not email or not password:
        print("错误: 缺少凭据。请设置 GOOGLE_PW 环境变量，格式为 '账号 密码'。")
        print("例如:")
        print("  export GOOGLE_PW='your.email@gmail.com your_password'")
        return
    
    try:
        browser = playwright.firefox.launch(headless=True)
        context = browser.new_context()
        
        # 尝试加载已保存的 cookies
        cookies_loaded = False
        if cookies_path.exists():
            try:
                print("尝试使用已保存的 cookies 登录...")
                with open(cookies_path, 'r') as f:
                    cookies = json.load(f)
                    context.add_cookies(cookies)
                cookies_loaded = True
            except Exception as e:
                print(f"加载 cookies 失败: {e}")
                print("将继续尝试密码登录...")
                cookies_loaded = False
        
        page = context.new_page()
        
        try:
            # 先访问目标页面，查看是否已登录
            print(f"访问目标页面: {app_url}")
            try:
                page.goto(app_url, timeout=60000)  # 增加超时时间到60秒
            except Exception as e:
                print(f"页面加载超时，但将继续执行: {e}")
            
            try:
                # 等待页面加载，但不中断脚本
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e:
                print(f"页面加载等待超时，但将继续执行: {e}")
            
            login_required = True
            
            # 检查是否需要登录 (通过页面URL判断)
            current_url = page.url
            if cookies_loaded:
                try:
                    # 检测登录状态：如果URL包含idx.google.com但不包含signin，则已登录成功
                    if "idx.google.com" in current_url and "signin" not in current_url:
                        print("已经通过cookies登录成功!")
                        login_required = False
                        
                        # 即使通过cookie登录成功，也保存最新的cookies
                        try:
                            print("保存最新的cookies...")
                            cookies = context.cookies()
                            with open(cookies_path, 'w') as f:
                                json.dump(cookies, f)
                        except Exception as e:
                            print(f"保存cookies失败，但将继续执行: {e}")
                    else:
                        print("Cookie登录失败，将尝试密码登录...")
                except Exception as e:
                    print(f"判断登录状态失败，但将继续尝试密码登录: {e}")
            
            # 如果需要登录
            if login_required:
                print("开始密码登录流程...")
                
                # 确保在登录页面
                if "signin" not in page.url:
                    try:
                        page.goto(app_url, timeout=60000)
                    except Exception as e:
                        print(f"跳转到登录页面失败，但将继续尝试: {e}")
                    
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except Exception as e:
                        print(f"等待页面加载状态失败，但将继续执行: {e}")
                
                # 输入邮箱 - 使用try/except确保即使出错也继续
                try:
                    print("输入邮箱...")
                    try:
                        email_field = page.get_by_label("Email or phone")
                        email_field.fill(email)
                    except Exception:
                        # 尝试备用方法查找邮箱输入框
                        try:
                            email_field = page.query_selector('input[type="email"]')
                            if email_field:
                                email_field.fill(email)
                            else:
                                print("无法找到邮箱输入框，但将继续执行")
                        except Exception as e:
                            print(f"填写邮箱失败: {e}，但将继续执行")
                    
                    # 尝试点击下一步按钮
                    try:
                        next_button = page.get_by_role("button", name="Next")
                        if next_button:
                            next_button.click()
                        else:
                            # 尝试备用方法查找下一步按钮
                            next_button = page.query_selector('button[jsname="LgbsSe"]')
                            if next_button:
                                next_button.click()
                            else:
                                print("无法找到下一步按钮，但将继续执行")
                    except Exception as e:
                        print(f"点击下一步按钮失败: {e}，但将继续执行")
                    
                    # 等待密码输入框出现
                    try:
                        page.wait_for_selector('input[type="password"]', state="visible", timeout=20000)
                    except Exception as e:
                        print(f"等待密码输入框超时: {e}，但将继续尝试")
                    
                    # 输入密码
                    print("输入密码...")
                    try:
                        password_field = page.get_by_label("Enter your password")
                        if password_field:
                            password_field.fill(password)
                        else:
                            # 尝试备用方法查找密码输入框
                            password_field = page.query_selector('input[type="password"]')
                            if password_field:
                                password_field.fill(password)
                            else:
                                print("无法找到密码输入框，但将继续执行")
                    except Exception as e:
                        print(f"填写密码失败: {e}，但将继续执行")
                    
                    # 尝试点击下一步按钮
                    try:
                        next_button = page.get_by_role("button", name="Next")
                        if next_button:
                            next_button.click()
                        else:
                            # 尝试备用方法查找下一步按钮
                            next_button = page.query_selector('button[jsname="LgbsSe"]')
                            if next_button:
                                next_button.click()
                            else:
                                print("无法找到密码页面的下一步按钮，但将继续执行")
                    except Exception as e:
                        print(f"点击密码页面的下一步按钮失败: {e}，但将继续执行")
                    
                    # 等待登录完成并跳转
                    print("等待登录完成...")
                    try:
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except Exception as e:
                        print(f"等待网络空闲超时: {e}，但将继续执行")
                    
                    # 使用与cookie登录相同的判断标准验证登录是否成功
                    current_url = page.url
                    if "idx.google.com" in current_url and "signin" not in current_url:
                        print("密码登录成功!")
                        
                        # 保存cookies以便下次使用
                        try:
                            print("保存cookies以供下次使用...")
                            cookies = context.cookies()
                            with open(cookies_path, 'w') as f:
                                json.dump(cookies, f)
                        except Exception as e:
                            print(f"保存cookies失败: {e}，但将继续执行")
                    else:
                        print(f"登录可能不成功，当前URL: {current_url}，但将继续执行")
                except Exception as e:
                    print(f"登录过程中发生错误: {e}，但将继续执行")
                    print(f"错误详情: {traceback.format_exc()}")
            
            # 无论是已登录还是刚登录，都跳转到目标URL
            print(f"导航到目标页面: {app_url}")
            try:
                page.goto(app_url, timeout=60000)
            except Exception as e:
                print(f"跳转到目标页面失败: {e}，但将继续执行")
            
            # 等待页面完全加载，包括所有资源和AJAX请求
            print("等待页面完全加载...")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"等待DOM加载完成超时: {e}，但将继续执行")
            
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e:
                print(f"等待网络空闲超时: {e}，但将继续执行")
            
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception as e:
                print(f"等待页面完全加载超时: {e}，但将继续执行")
            
            # 最终验证是否成功访问目标URL
            current_url = page.url
            print(f"当前URL: {current_url}")
            
            # 使用统一的判断标准来验证最终访问是否成功
            if "idx.google.com" in current_url and "signin" not in current_url:
                # 最后再次保存cookies，确保获取最新状态
                try:
                    print("保存最终的cookies状态...")
                    cookies = context.cookies()
                    with open(cookies_path, 'w') as f:
                        json.dump(cookies, f)
                    print("Cookies保存成功!")
                except Exception as e:
                    print(f"保存最终cookies失败: {e}，但将继续执行")
                    
                print("成功访问目标页面！")
                print("等待30秒后关闭...")
                time.sleep(30)  # 等待30秒
                print("自动化流程完成!")
            else:
                print(f"警告: 当前页面URL ({current_url}) 与目标URL不完全匹配")
                print(f"登录可能部分成功或被重定向到其他页面，但脚本已完成执行")
            
        except Exception as e:
            print(f"页面交互过程中发生错误: {e}")
            print(f"错误详情: {traceback.format_exc()}")
            print("继续执行...")
        finally:
            try:
                # 无论如何都等待30秒后关闭
                print("等待30秒后关闭...")
                time.sleep(30)
            except Exception:
                pass
    except Exception as e:
        print(f"浏览器初始化过程中发生错误: {e}")
        print(f"错误详情: {traceback.format_exc()}")
    finally:
        try:
            page.close()
        except Exception:
            pass
        
        try:
            context.close()
        except Exception:
            pass
        
        try:
            browser.close()
        except Exception:
            pass
        
        print("脚本执行完毕!")

if __name__ == "__main__":
    try:
        with sync_playwright() as playwright:
            run(playwright)
    except Exception as e:
        print(f"Playwright启动失败: {e}")
        print(f"错误详情: {traceback.format_exc()}")
        print("脚本终止")
