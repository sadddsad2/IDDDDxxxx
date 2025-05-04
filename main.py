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

def wait_for_element_with_retry(page, locator, description, timeout_seconds=10, max_attempts=3):
    """尝试等待元素出现，如果超时则返回False，成功则返回True"""
    for attempt in range(max_attempts):
        try:
            print(f"等待{description}出现，第{attempt + 1}次尝试...")
            element = page.locator(locator).wait_for(state="visible", timeout=timeout_seconds * 1000)
            print(f"? {description}已出现!")
            return True
        except Exception as e:
            print(f"× 等待{description}超时: {e}")
            if attempt < max_attempts - 1:
                print("准备重试...")
            else:
                print(f"已达到最大尝试次数({max_attempts})，无法找到{description}")
                return False
    return False

def refresh_page_and_wait(page, url, refresh_attempts=3, total_wait_time=240):
    """刷新页面并等待指定元素，总共尝试指定次数"""
    start_time = time.time()
    elapsed_time = 0
    refresh_count = 0
    
    web_button_found = False
    starting_server_found = False
    
    while elapsed_time < total_wait_time and refresh_count < refresh_attempts:
        # 如果两个元素都未找到，刷新页面
        if not (web_button_found and starting_server_found):
            print(f"刷新页面，第{refresh_count + 1}次尝试...")
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception as e:
                print(f"页面刷新或加载失败: {e}，但将继续执行")
            
            refresh_count += 1
        
        # 尝试查找Web按钮
        if not web_button_found:
            try:
                web_button_selector = "#iframe-container iframe >> nth=0"
                frame = page.frame_locator(web_button_selector)
                if frame:
                    web_button = frame.get_by_text("Web", exact=True)
                    if web_button:
                        time.sleep(20)
                        print("找到Web按钮，点击...")
                        web_button.click()
                        web_button_found = True
                    else:
                        print("找不到Web按钮")
                else:
                    print("找不到包含Web按钮的框架")
            except Exception as e:
                print(f"查找或点击Web按钮失败: {e}")
        
        # 尝试查找Starting server文本
        if web_button_found and not starting_server_found:
            try:
                # 给页面一些时间来响应Web按钮点击
                time.sleep(3)
                
                starting_server_selector = "#iframe-container iframe >> nth=0"
                iframe_chain = page.frame_locator(starting_server_selector)
                
                # 尝试通过多层iframe定位Starting server文本
                try:
                    inner_frame = iframe_chain.frame_locator("iframe[name=\"ded0e382-bedf-478d-a870-33bb6cadac6f\"]")
                    if inner_frame:
                        web_frame = inner_frame.frame_locator("iframe[title=\"Web\"]")
                        if web_frame:
                            preview_frame = web_frame.frame_locator("#previewFrame")
                            if preview_frame:
                                starting_server = preview_frame.get_by_role("heading", name="Starting server")
                                if starting_server:
                                    print("找到Starting server文本")
                                    starting_server_found = True
                                else:
                                    print("找不到Starting server文本")
                            else:
                                print("找不到预览框架")
                        else:
                            print("找不到Web框架")
                    else:
                        print("找不到内部框架")
                except Exception as e:
                    print(f"通过多层iframe查找Starting server失败: {e}")
                    
                # 如果上面的方法失败，尝试直接在可见的框架中搜索
                if not starting_server_found:
                    try:
                        all_frames = page.frames
                        for frame in all_frames:
                            try:
                                heading = frame.get_by_role("heading", name="Starting server")
                                if heading:
                                    print("通过框架搜索找到Starting server文本")
                                    starting_server_found = True
                                    break
                            except:
                                continue
                    except Exception as e:
                        print(f"通过遍历所有框架查找Starting server")
            except Exception as e:
                print(f"查找或点击Starting server文本失败")
        
        # 如果两个元素都找到了，跳出循环
        if web_button_found and starting_server_found:
            print("Web按钮和Starting server文本都已找到")
            break
        
        # 短暂等待后继续尝试
        time.sleep(5)
        elapsed_time = time.time() - start_time
        print(f"已经等待了 {int(elapsed_time)} 秒，剩余等待时间 {int(total_wait_time - elapsed_time)} 秒")
    
    # 返回两个元素是否都找到
    return web_button_found and starting_server_found

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
        browser = playwright.firefox.launch(headless=False)
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
            print(f"访问目标页面")
            try:
                page.goto(app_url, timeout=30000) 
            except Exception as e:
                print(f"页面加载超时")
            
            login_required = True
            
            # 检查是否需要登录 (通过页面URL判断)
            current_url = page.url
            if cookies_loaded:
                try:
                    # 检测登录状态：如果URL包含idx.google.com但不包含signin，则已登录成功
                    if "idx.google.com" in current_url and "signin" not in current_url:
                        print("已经通过cookies登录成功!")
                        login_required = False

                    else:
                        print("Cookie登录失败，将尝试密码登录")
                except Exception as e:
                    print(f"判断登录状态失败，但将继续尝试密码登录")
            
            # 如果需要登录
            if login_required:
                print("开始密码登录流程...")
                
                # 确保在登录页面
                if "signin" not in page.url:
                    try:
                        page.goto(app_url, timeout=60000)
                    except Exception as e:
                        print(f"跳转到登录页面失败，但将继续尝试")
                    
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=60000)
                        page.wait_for_load_state("networkidle", timeout=60000)
                    except Exception as e:
                        print(f"等待页面加载状态失败，但将继续执行")
                
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
                            print(f"填写邮箱失败，但将继续执行")
                    
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
                        print(f"点击下一步按钮失败，但将继续执行")
                    
                    # 等待密码输入框出现
                    try:
                        page.wait_for_selector('input[type="password"]', state="visible", timeout=20000)
                    except Exception as e:
                        print(f"等待密码输入框超时，但将继续尝试")
                    
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
                        print(f"填写密码失败，但将继续执行")
                    
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
                        print(f"点击密码页面的下一步按钮失败，但将继续执行")
                    
                    # 等待登录完成并跳转
                    print("等待登录完成...")
                    try:
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except Exception as e:
                        print(f"等待网络空闲超时，但将继续执行")
                    
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
            print(f"导航到目标页面")
            try:
                page.goto(app_url, timeout=30000)
            except Exception as e:
                print(f"跳转到目标页面失败,但将继续执行")
            
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
                
                # 使用增强的等待和刷新函数，尝试找到Web按钮和Starting server文本
                elements_found = refresh_page_and_wait(page, app_url, refresh_attempts=5, total_wait_time=120)
                
                if elements_found:
                    print("成功点击Web按钮和Starting server文本，等待20秒后退出...")
                    time.sleep(20)
                else:
                    print("在120秒内未能找到Web按钮和Starting server文本，但将继续等待")
                
            else:
                print(f"警告: 当前页面URL与目标URL不完全匹配")
                print(f"登录可能部分成功或被重定向到其他页面，但脚本已完成执行")
            
        except Exception as e:
            print(f"页面交互过程中发生错误")
        finally:
            try:
                print("自动化流程完成!")
            except Exception:
                pass
    except Exception as e:
        print(f"浏览器初始化过程中发生错误")
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
