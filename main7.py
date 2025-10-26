import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import json
import os
import requests
from datetime import datetime

COOKIE_FILE = "railway_cookies.json"

def get_credentials():
    """从环境变量或默认值获取账号密码"""
    pw_env = os.environ.get('PW', 'cff@koyeb.nyc.mn M{}2WVH_~8Nu')
    try:
        username, password = pw_env.split(' ', 1)
        print(f"? 使用账号: {username}")
        return username, password
    except ValueError:
        print("? 账号密码格式错误，应为: 账号 密码")
        return None, None

def get_git_repo():
    """从环境变量或默认值获取Git仓库"""
    repo = os.environ.get('GIT_REPO', 'gryyyh/raiyway')
    print(f"? 使用仓库: {repo}")
    return repo

def get_telegram_config():
    """从环境变量或默认值获取Telegram配置"""
    tg_env = os.environ.get('TG', '')
    
    if not tg_env:
        print("? 未配置Telegram通知 (TG环境变量为空)")
        return None, None
    
    try:
        chat_id, bot_token = tg_env.split(' ', 1)
        print(f"? Telegram配置已加载 (Chat ID: {chat_id[:8]}...)")
        return chat_id, bot_token
    except ValueError:
        print("? Telegram配置格式错误，应为: CHAT_ID BOT_TOKEN")
        return None, None

def send_telegram_notification(success, message=""):
    """发送Telegram通知"""
    chat_id, bot_token = get_telegram_config()
    
    if not chat_id or not bot_token:
        print("? 跳过Telegram通知（未配置或配置错误）")
        return False
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "? 部署成功" if success else "? 部署失败"
    
    text = f"""
?? Railway部署通知

? 时间: {current_time}
?? 状态: {status}
"""
    
    if message:
        text += f"\n?? 详情: {message}"
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("? Telegram通知发送成功")
            return True
        else:
            print(f"? Telegram通知发送失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"? Telegram通知发送异常: {e}")
        return False

def save_cookies(context, filepath):
    """保存cookies到文件"""
    cookies = context.cookies()
    with open(filepath, 'w') as f:
        json.dump(cookies, f)
    print(f"? Cookies已保存到 {filepath}")

def load_cookies(context, filepath):
    """从文件加载cookies"""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"? Cookies已从 {filepath} 加载")
        return True
    else:
        print(f"? Cookie文件不存在: {filepath}")
        return False

def delete_cookies(filepath):
    """删除cookies文件"""
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"? Cookies文件已删除: {filepath}")
        return True
    else:
        print(f"? Cookie文件不存在，无需删除: {filepath}")
        return False

def handle_github_authorization(page):
    """处理GitHub授权页面（容错处理）"""
    try:
        time.sleep(3)
        current_url = page.url
        
        if "github.com" in current_url:
            if "authorize" in current_url.lower() or "oauth" in current_url.lower():
                print("? 检测到GitHub授权页面，正在授权...")
                try:
                    authorize_button = page.get_by_role("button", name=re.compile("Authorize", re.IGNORECASE))
                    authorize_button.click()
                    print("? 已点击授权按钮")
                    time.sleep(5)
                    print(f"授权后URL: {page.url}")
                    return True
                except Exception as e:
                    print(f"? 授权处理异常（已忽略）: {e}")
                    return False
        return False
    except Exception as e:
        print(f"? GitHub授权检查异常（已忽略）: {e}")
        return False

def check_login_status(page):
    """检查是否已登录（通过访问dashboard判断）（容错处理）"""
    try:
        page.goto("https://railway.com/login")
        time.sleep(10)
        current_url = page.url
        if "dashboard" in current_url:
            print("? Cookie登录成功！已到达dashboard")
            time.sleep(3)
            try:
                page.get_by_role("button", name="Continue with GitHub").click()
                print("? 已点击 Continue with GitHub")
                
                # 处理可能的GitHub授权
                handle_github_authorization(page)
                
                # 再次检查是否回到dashboard
                time.sleep(3)
                current_url = page.url
                if "railway.com" in current_url and "github.com" not in current_url:
                    print("? GitHub连接确认完成")
                    return True
                    
            except Exception as e:
                print(f"? Continue with GitHub 操作异常（已忽略）: {e}")
            return True
        else:
            print(f"? Cookie登录失败，当前URL: {current_url}")
            return False
    except Exception as e:
        print(f"? Cookie验证异常（已忽略）: {e}")
        return False

def login_with_credentials(page, context, username, password):
    """使用账号密码登录（容错处理）"""
    print("开始账号密码登录...")
    try:
        page.goto("https://railway.com/login")
        page.get_by_role("button", name="Continue with GitHub").click()
        page.get_by_label("Username or email address").fill(username)
        page.get_by_label("Password").click()
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in", exact=True).click()
        
        # 等待20秒并检查登录状态
        print("等待登录中...")
        time.sleep(20)
        
        # 检查当前URL状态
        current_url = page.url
        print(f"当前URL: {current_url}")
        
        # 处理GitHub授权
        handle_github_authorization(page)
        
        # 再次检查是否成功跳转到dashboard
        time.sleep(3)
        current_url = page.url
        if "railway.com/dashboard" in current_url:
            print("? 登录成功！已到达dashboard")
            # 登录成功后保存cookie
            save_cookies(context, COOKIE_FILE)
            time.sleep(5)
            return True
        else:
            print(f"? 当前页面: {current_url}")
            # 如果还没到dashboard，尝试手动跳转
            if "railway.com" in current_url and "dashboard" not in current_url:
                print("尝试手动跳转到dashboard...")
                try:
                    page.goto("https://railway.com/dashboard")
                    time.sleep(3)
                    if "dashboard" in page.url:
                        print("? 跳转成功")
                        save_cookies(context, COOKIE_FILE)
                        time.sleep(5)
                        return True
                except Exception as e:
                    print(f"? 手动跳转异常（已忽略）: {e}")
        
        return False
    except Exception as e:
        print(f"? 登录过程异常（已忽略）: {e}")
        return False

def check_has_projects(page):
    """检查dashboard是否有项目（容错处理）"""
    try:
        page.goto("https://railway.com/dashboard", wait_until="networkidle", timeout=10000)
        time.sleep(3)
        
        # 方式1: 检查是否显示"Create a New Project"（无项目状态）
        try:
            page_content = page.content()
            if "Create a New Project" in page_content:
                print("? 检测到 'Create a New Project'，dashboard无项目")
                return False
            if "Deploy a GitHub Repository, Provision a Database" in page_content:
                print("? 检测到空项目引导文本，dashboard无项目")
                return False
        except Exception as e:
            print(f"方式1检测失败（已忽略）: {e}")
        
        # 方式2: 查找项目链接（有项目时会有这些链接）
        try:
            project_links = page.locator("a[href*='/project/']").count()
            if project_links > 0:
                print(f"? 检测到 {project_links} 个项目链接，说明有项目")
                return True
        except Exception as e:
            print(f"方式2检测失败（已忽略）: {e}")
        
        # 方式3: 查找项目卡片或列表（有项目时会显示）
        try:
            projects = page.locator("[data-id='project-card'], .project-card").count()
            if projects > 0:
                print(f"? 检测到 {projects} 个项目卡片，说明有项目")
                return True
        except Exception as e:
            print(f"方式3检测失败（已忽略）: {e}")
        
        # 方式4: 查找是否有GitHub图标按钮（Create a New Project区域的按钮）
        try:
            github_repo_text = page.get_by_text("Deploy a GitHub Repository").count()
            if github_repo_text > 0:
                print("? 检测到创建项目引导界面，dashboard无项目")
                return False
        except Exception as e:
            print(f"方式4检测失败（已忽略）: {e}")
        
        # 方式5: 检查是否有"New Project"按钮在顶部导航（有项目时才显示）
        try:
            new_project_nav = page.locator("button:has-text('New Project'), a:has-text('New Project')").count()
            if new_project_nav > 0:
                print("? 检测到导航栏的 'New Project' 按钮，说明已有项目")
                return True
        except Exception as e:
            print(f"方式5检测失败（已忽略）: {e}")
        
        print("? 未明确检测到项目，假设无项目")
        return False
        
    except Exception as e:
        print(f"? 检查项目异常（已忽略，假设无项目）: {e}")
        return False

def delete_account(page, max_retries=3):
    """删除账户，重试直到成功（使用两次回车确认）（容错处理）"""
    for attempt in range(1, max_retries + 1):
        print(f"\n尝试删除账户 (第 {attempt}/{max_retries} 次)...")
        
        try:
            try:
                page.goto("https://railway.com/account")
                time.sleep(2)
            except Exception as e:
                print(f"? 访问account页面异常（已忽略）: {e}")
            
            try:
                page.get_by_role("button", name="Delete Account").click()
                time.sleep(2)
            except Exception as e:
                print(f"? 点击Delete Account按钮异常（已忽略）: {e}")
            
            try:
                # 输入邮箱并确保输入框获得焦点
                page.get_by_label("Confirm text").click()
                page.get_by_label("Confirm text").press("ControlOrMeta+a")
                page.get_by_label("Confirm text").fill("cff@koyeb.nyc.mn")
                page.once("dialog", lambda dialog: dialog.dismiss())
                page.get_by_label("Confirm text").press("Enter")
                time.sleep(2)
                page.keyboard.press("Enter")
                
                # 第一次回车：在输入框上按回车
                print("第一次按回车：提交表单...")
                # confirm_input.press("Enter")
                # time.sleep(3)  # 等待页面响应
                
                # 检查是否跳转到首页（说明删除失败）
                current_url = page.url
                print(f"第一次回车后URL: {current_url}")
                
                if current_url == "https://railway.com/" or current_url == "https://railway.com":
                    print("? 第一次回车后跳转到首页，删除失败！")
                    if attempt < max_retries:
                        print(f"等待3秒后重试...")
                        time.sleep(3)
                        continue
                    else:
                        return False
                
                # 没有跳转到首页，检查是否有确认对话框
                print("? 未跳转到首页，检查是否有确认对话框...")
                
                # 第二次回车：确认删除对话框
                print("第二次按回车：确认删除...")
                page.keyboard.press("Enter")
                time.sleep(2)
                
                print("? 已连续按两次回车键确认删除")
                
            except Exception as e:
                print(f"? 输入邮箱或按回车异常（已忽略）: {e}")
            
            # 等待页面跳转
            print("等待删除结果...")
            time.sleep(5)
            
            try:
                # 检查是否跳转到railway.com首页
                current_url = page.url
                print(f"删除后URL: {current_url}")
                
                if current_url == "https://railway.com/" or current_url == "https://railway.com":
                    print("? 账户删除成功！已跳转到首页")
                    return True
                else:
                    print(f"? 删除可能失败，未跳转到首页，当前URL: {current_url}")
                    if attempt < max_retries:
                        print(f"等待3秒后重试...")
                        time.sleep(3)
            except Exception as e:
                print(f"? 检查删除结果异常（已忽略）: {e}")
                if attempt < max_retries:
                    time.sleep(3)
                    
        except Exception as e:
            print(f"? 删除账户异常（已忽略）: {e}")
            if attempt < max_retries:
                print(f"等待3秒后重试...")
                time.sleep(3)
    
    print(f"? 账户删除失败，已重试 {max_retries} 次")
    return False

def run(playwright: Playwright) -> None:
    # 获取账号密码和仓库
    username, password = get_credentials()
    if not username or not password:
        print("? 无法获取有效的账号密码，脚本终止")
        return
    
    git_repo = get_git_repo()
    
    browser = playwright.firefox.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    deploy_success = False
    error_message = ""
    
    try:
        # 尝试使用cookie登录
        login_success = False
        cookie_loaded = False
        
        try:
            cookie_loaded = load_cookies(context, COOKIE_FILE)
        except Exception as e:
            print(f"? 加载Cookie异常（已忽略）: {e}")
        
        if cookie_loaded:
            print("尝试使用Cookie登录...")
            try:
                login_success = check_login_status(page)
                # Cookie登录成功后也保存一次（更新cookie）
                if login_success:
                    try:
                        save_cookies(context, COOKIE_FILE)
                    except Exception as e:
                        print(f"? 保存Cookie异常（已忽略）: {e}")
            except Exception as e:
                print(f"? Cookie登录检查异常（已忽略）: {e}")
        
        # 如果cookie登录失败，使用账号密码登录
        if not login_success:
            print("Cookie登录失败，使用账号密码登录...")
            try:
                login_success = login_with_credentials(page, context, username, password)
            except Exception as e:
                print(f"? 账号密码登录异常（已忽略）: {e}")
        
        if not login_success:
            error_message = "登录失败"
            print(f"? {error_message}，但继续尝试执行...")
        
        # 检查是否有项目
        print("\n检查dashboard是否有项目...")
        has_projects = False
        try:
            has_projects = check_has_projects(page)
        except Exception as e:
            print(f"? 检查项目异常（已忽略，假设无项目）: {e}")
        
        if has_projects:
            print("? 检测到已有项目，需要删除账户重新部署")
            
            # 删除账户（带重试机制）
            delete_success = delete_account(page, max_retries=3)
            
            if not delete_success:
                error_message = "账户删除失败，请手动删除"
                print(f"? {error_message}")
                send_telegram_notification(False, error_message)
                page.close()
                context.close()
                browser.close()
                return
            else:
                # 删除成功后删除Cookie文件
                print("\n账户删除成功，删除Cookie文件...")
                try:
                    delete_cookies(COOKIE_FILE)
                except Exception as e:
                    print(f"? 删除Cookie异常（已忽略）: {e}")

            # 再次登录创建新账户
            print("登录以创建新账户...")
            try:
                page.goto("https://railway.com/login")
                time.sleep(3)
                page.get_by_role("button", name="Continue with GitHub").click()
                
                # 等待自动登录或手动登录
                time.sleep(3)
                current_url = page.url
                
                # 如果还在GitHub登录页面，填写账号密码
                if "github.com" in current_url:
                    print("需要重新登录GitHub...")
                    try:
                        page.get_by_label("Username or email address").fill(username)
                        page.get_by_label("Password").click()
                        page.get_by_label("Password").fill(password)
                        page.get_by_role("button", name="Sign in", exact=True).click()
                        time.sleep(10)
                    except Exception as e:
                        print(f"? GitHub登录异常（已忽略）: {e}")
            except Exception as e:
                print(f"? 重新登录异常（已忽略）: {e}")
            
            # 尝试点击"I agree with Railway's Terms"（如果存在）
            print("检查是否需要同意条款...")
            try:
                terms_button = page.get_by_role("button", name="I agree with Railway's Terms")
                if terms_button.is_visible(timeout=3000):
                    terms_button.scroll_into_view_if_needed()
                    time.sleep(1)
                    terms_button.click()
                    print("? 已同意条款")
                else:
                    print("? 未找到条款按钮，可能不需要同意")
            except Exception as e:
                print(f"? 条款按钮处理异常（已忽略）: {e}")
            
            # 尝试点击"I will not deploy any of that"（如果存在）
            print("检查是否需要确认部署政策...")
            try:
                deploy_button = page.get_by_role("button", name="I will not deploy any of that")
                if deploy_button.is_visible(timeout=3000):
                    deploy_button.scroll_into_view_if_needed()
                    time.sleep(1)
                    deploy_button.click()
                    print("? 已确认部署政策")
                else:
                    print("? 未找到部署政策按钮，可能不需要确认")
            except Exception as e:
                print(f"? 部署政策按钮处理异常（已忽略）: {e}")
            
            # 再次检查是否还有项目（验证删除是否成功）
            print("\n验证账户删除是否成功...")
            try:
                time.sleep(3)
                still_has_projects = check_has_projects(page)
                
                if still_has_projects:
                    error_message = "删除账户后仍检测到项目存在，删除失败！请手动删除账户后重试"
                    print(f"? {error_message}")
                    send_telegram_notification(False, error_message)
                    page.close()
                    context.close()
                    browser.close()
                    return
                else:
                    print("? 确认账户已成功删除，继续部署新项目")
            except Exception as e:
                print(f"? 验证删除结果异常（已忽略，继续部署）: {e}")
        else:
            print("? 未检测到项目，直接部署新项目")
        
        # 部署新项目前再次确认无项目（最终检查）
        print("\n部署前最终检查是否存在项目...")
        try:
            final_check_has_projects = check_has_projects(page)
            
            if final_check_has_projects:
                error_message = "部署前检测到项目存在，账号删除失败！请手动删除账户后重试"
                print(f"? {error_message}")
                send_telegram_notification(False, error_message)
                page.close()
                context.close()
                browser.close()
                return
            else:
                print("? 最终确认无项目，开始部署")
        except Exception as e:
            print(f"? 最终检查异常（已忽略，继续部署）: {e}")
        
        # 部署新项目
        print("选择GitHub Repository...")
        try:
            page.goto("https://railway.com/new")
            try:
                page.get_by_text("GitHub Repository").click()
                print("等待GitHub Repository加载（10秒）...")
                time.sleep(10)
                
                print(f"选择仓库: {git_repo}")
                page.get_by_text(git_repo).click()
                print("? 仓库选择完成")
                
                # 等待项目创建完成
                time.sleep(5)
                
                # 部署成功
                deploy_success = True
                print("\n? 部署成功！")
                
                # 部署完成后保存Cookie
                print("部署完成，保存Cookie...")
                try:
                    save_cookies(context, COOKIE_FILE)
                except Exception as e:
                    print(f"? 保存Cookie异常（已忽略）: {e}")
                
                send_telegram_notification(True, f"仓库: {git_repo}")
                
            except Exception as e:
                error_message = f"GitHub Repository操作失败: {str(e)}"
                print(f"? {error_message}")
                print("? 尝试继续执行...")
                send_telegram_notification(False, error_message)
        except Exception as e:
            error_message = f"访问new页面失败: {str(e)}"
            print(f"? {error_message}")
            send_telegram_notification(False, error_message)
        
        time.sleep(3)
        
    except Exception as e:
        error_message = f"脚本执行异常: {str(e)}"
        print(f"? {error_message}")
        print("? 尽管出现异常，但尝试完成清理工作...")
        try:
            send_telegram_notification(False, error_message)
        except Exception as notify_error:
            print(f"? Telegram通知发送异常（已忽略）: {notify_error}")
    
    finally:
        try:
            page.close()
        except Exception as e:
            print(f"? 关闭页面异常（已忽略）: {e}")
        
        try:
            context.close()
        except Exception as e:
            print(f"? 关闭context异常（已忽略）: {e}")
        
        try:
            browser.close()
        except Exception as e:
            print(f"? 关闭浏览器异常（已忽略）: {e}")
        
        print("\n? 脚本执行完成")

with sync_playwright() as playwright:
    run(playwright)
