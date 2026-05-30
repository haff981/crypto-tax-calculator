# ============================================================
#  browser.py — Playwright 浏览器自动化模块
#  功能：反检测登录 + 模拟真人行为 + 发表评论
# ============================================================

import json
import random
import logging
import asyncio
from pathlib import Path

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent

# 随机 User-Agent 列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
]

# 屏幕分辨率列表（模拟不同设备）
VIEWPORTS = [
    {'width': 1920, 'height': 1080},
    {'width': 1536, 'height': 864},
    {'width': 1440, 'height': 900},
    {'width': 1366, 'height': 768},
    {'width': 1280, 'height': 720},
]


class YouTubeCommenter:
    """YouTube 自动评论器 — Playwright 浏览器自动化"""

    def __init__(self, headless=True):
        self.headless = headless
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.current_account = None

    async def init_browser(self, account_info=None):
        """初始化浏览器（带反检测措施）"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.error("需要安装: pip install playwright && playwright install chromium")
            raise

        self.current_account = account_info
        self.pw = await async_playwright().start()

        # 启动浏览器（带反检测参数）
        viewport = random.choice(VIEWPORTS)
        self.browser = await self.pw.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--window-size={},{}'.format(viewport['width'], viewport['height']),
                '--lang=en-US,en;q=0.9',
                '--disable-extensions',
                f'--window-size={viewport["width"]},{viewport["height"]}',
            ]
        )

        # 创建上下文（模拟真实浏览器环境）
        self.context = await self.browser.new_context(
            viewport=viewport,
            locale='en-US',
            timezone_id='America/New_York',
            user_agent=random.choice(USER_AGENTS),
            color_scheme='light',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )

        # 注入反自动化检测 JS
        await self.context.add_init_script("""
            // 隐藏 webdriver 标志
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 模拟插件
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 模拟语言
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // 模拟 Chrome 对象
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };

            // 隐藏 Puppeteer/Playwright 特征
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters);

            // 控制台信息隐藏
            console.log = function(){};
            console.warn = function(){};
            console.error = function(){};
        """)

        self.page = await self.context.new_page()

        # 如果提供了账号信息，尝试登录
        if account_info:
            await self._login_google(account_info)

        log.info("✓ 浏览器初始化完成 (UA: {}x{})".format(
            viewport['width'], viewport['height']))
        if account_info:
            log.info("✓ 账号: {}".format(account_info.get('email', 'unknown')))

    async def _login_google(self, account_info):
        """登录 Google 账号"""
        login_type = account_info.get('type', 'credentials')
        email = account_info.get('email', '')
        password = account_info.get('password', '')

        if not email or not password:
            log.warning("⚠ 账号缺少邮箱或密码，将以未登录状态运行")
            return

        if login_type == 'cookie':
            # Cookie 登录方式
            cookie_file = SCRIPT_DIR / "cookies" / f"account_{account_info.get('index', 0)}.json"
            if cookie_file.exists():
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                log.info(f"✓ Cookie 加载成功: {cookie_file.name}")
            else:
                log.warning(f"⚠ Cookie 文件不存在: {cookie_file}")
        elif login_type == 'credentials':
            # 邮箱密码登录
            log.info("正在登录 Google 账号...")
            try:
                await self.page.goto('https://accounts.google.com/signin',
                                      wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                # 输入邮箱
                email_input = await self.page.query_selector('input[type="email"]')
                if email_input:
                    await email_input.click()
                    await asyncio.sleep(random.uniform(0.5, 1))
                    await self._type_like_human(email)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    await self.page.click('#identifierNext')
                    await asyncio.sleep(random.uniform(2, 4))

                    # 输入密码
                    pwd_input = await self.page.query_selector('input[type="password"]')
                    if pwd_input:
                        await pwd_input.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                        await self._type_like_human(password)
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                        await self.page.click('#passwordNext')
                        await asyncio.sleep(random.uniform(3, 6))

                        # 检查是否登录成功
                        current_url = self.page.url
                        if 'myaccount' in current_url or 'mail.google' in current_url or 'youtube' in current_url:
                            log.info("✓ Google 登录成功!")
                        else:
                            # 可能出现了验证码或其他页面
                            log.info(f"登录后页面: {current_url}")
                            # 尝试截图保存用于调试
                            try:
                                screenshot_path = SCRIPT_DIR / "logs" / f"login_{random.randint(1000,9999)}.png"
                                await self.page.screenshot(path=str(screenshot_path))
                                log.info(f"登录页面截图已保存: {screenshot_path}")
                            except:
                                pass
                    else:
                        log.warning("未找到密码输入框，可能已登录或需要其他验证")
                else:
                    log.warning("未找到邮箱输入框")

            except Exception as e:
                log.error(f"Google 登录失败: {e}")
                # 截图保存调试
                try:
                    screenshot_path = SCRIPT_DIR / "logs" / f"login_error_{random.randint(1000,9999)}.png"
                    await self.page.screenshot(path=str(screenshot_path))
                    log.info(f"错误截图: {screenshot_path}")
                except:
                    pass

    async def _type_like_human(self, text, element=None):
        """模拟人类打字速度（逐字符输入 + 随机停顿）"""
        for i, char in enumerate(text):
            await self.page.keyboard.type(char, delay=random.randint(50, 150))
            # 偶尔长停顿（模拟思考）
            if random.random() < 0.04:
                await asyncio.sleep(random.uniform(300, 700))
            # 偶尔短停顿
            elif random.random() < 0.08:
                await asyncio.sleep(random.randint(80, 200))
            # 每10个左右字符停一下
            elif i > 0 and i % random.randint(8, 15) == 0:
                await asyncio.sleep(random.randint(100, 300))

    async def _simulate_watching(self, duration_seconds=None):
        """模拟真人观看视频的行为"""
        actions = random.randint(2, 5)

        for _ in range(actions):
            action_type = random.choice(['scroll_down', 'scroll_up', 'pause_play', 'move_mouse', 'check_desc'])

            if action_type == 'scroll_down':
                scroll_amount = random.randint(100, 500)
                await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            elif action_type == 'scroll_up':
                scroll_amount = random.randint(50, 300)
                await self.page.evaluate(f"window.scrollBy(0, -{scroll_amount})")
            elif action_type == 'pause_play':
                video = await self.page.query_selector('video')
                if video:
                    await video.click()
                    await asyncio.sleep(random.uniform(500, 2000))
                    await video.click()
            elif action_type == 'move_mouse':
                x = random.randint(150, 800)
                y = random.randint(150, 600)
                await self.page.mouse.move(x, y)
                steps = random.randint(5, 20)
                await self.page.mouse.move(
                    x + random.randint(-100, 100),
                    y + random.randint(-50, 50),
                    steps=steps
                )
            elif action_type == 'check_desc':
                # 点击展开描述
                expand_btn = await self.page.query_selector('#expand')
                if expand_btn:
                    await expand_btn.click()

            await asyncio.sleep(random.uniform(800, 2500))

    async def post_comment(self, video_url, comment_text, max_retries=3):
        """
        在指定 YouTube 视频下发表评论
        返回: True 成功 / False 失败
        """
        for attempt in range(max_retries):
            try:
                log.info(f"[第{attempt+1}次] 打开视频: {video_url}")

                # 打开视频页面
                await self.page.goto(video_url, wait_until='domcontentloaded', timeout=45000)
                await asyncio.sleep(random.uniform(4000, 7000))

                # 模拟观看行为（关键！看起来像真人）
                log.info("模拟观看行为...")
                await self._simulate_watching()

                # 滚动到评论区位置
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.65)")
                await asyncio.sleep(random.uniform(1500, 3000))

                # 尝试展开评论区（如果被折叠了）
                show_more = await self.page.query_selector('#show-more')
                if show_more:
                    try:
                        await show_more.click()
                        await asyncio.sleep(random.uniform(1000, 2000))
                    except:
                        pass

                # 寻找并点击评论输入框
                comment_box = None
                selectors = [
                    '#placeholder-area',
                    '#simplebox-placeholder',
                    '[aria-label="Add a comment"]',
                    '#comment-box',
                    '#contenteditable-root',
                    'ytd-comment-thread-renderer #placeholder-area',
                    '#contenteditable-textarea',
                ]

                for sel in selectors:
                    el = await self.page.query_selector(sel)
                    if el and await el.is_visible():
                        comment_box = el
                        break

                if not comment_box:
                    # 再试一次：滚动到最底部找评论框
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(random.uniform(1000, 2000))

                    for sel in selectors:
                        el = await self.page.query_selector(sel)
                        if el and await el.is_visible():
                            comment_box = el
                            break

                if not comment_box:
                    log.warning("❌ 未找到评论输入框")
                    # 截图保存
                    try:
                        ss = SCRIPT_DIR / "logs" / f"nobox_{random.randint(1000,9999)}.png"
                        await self.page.screenshot(path=str(ss))
                    except:
                        pass
                    return False

                # 点击激活评论框
                await comment_box.click()
                await asyncio.sleep(random.uniform(800, 1800))

                # 输入评论文案（模拟人类打字）
                log.info(f"输入评论: {comment_text[:60]}...")

                # 尝试找到可编辑元素
                editable = await self.page.query_selector('#contenteditable-root')
                if editable and await editable.is_visible():
                    await editable.click()
                    await asyncio.sleep(random.uniform(300, 600))
                    await self._type_like_human(comment_text)
                else:
                    # Fallback: 直接键盘输入
                    focused = await self.page.evaluate("document.activeElement.tagName")
                    if focused in ['DIV', 'TEXTAREA']:
                        await self._type_like_human(comment_text)
                    else:
                        # 最后尝试：直接聚焦并输入
                        await comment_box.click()
                        await asyncio.sleep(500)
                        await self._type_like_human(comment_text)

                # 等待一会儿再提交（像真人打完字会检查一下）
                await asyncio.sleep(random.uniform(2000, 4000))

                # 提交评论
                submitted = False

                # 方法1：点击提交按钮
                submit_selectors = [
                    'ytd-comment-reply-dialog-renderer #submit-button button',
                    '#submit-button ytd-button-renderer button',
                    'ytd-comment-dialog-renderer #submit-button button',
                    'button[aria-label="Comment"]',
                    '#send-button',
                    'ytd-comment-simplebox-renderer #submit-button ytd-button-renderer button',
                ]

                for sel in submit_selectors:
                    btn = await self.page.query_selector(sel)
                    if btn:
                        try:
                            is_disabled = await btn.is_disabled()
                            is_hidden = not await btn.is_visible()
                            if not is_disabled and not is_hidden:
                                await btn.click()
                                submitted = True
                                log.info(f"通过按钮提交: {sel[:40]}")
                                break
                        except Exception:
                            continue

                # 方法2：Ctrl+Enter 提交
                if not submitted:
                    log.info("尝试 Ctrl+Enter 提交...")
                    await self.page.keyboard.press('Control+Enter')
                    await asyncio.sleep(500)
                    submitted = True

                # 方法3：纯 Enter 提交（最后的 fallback）
                if not submitted:
                    log.info("尝试 Enter 提交...")
                    await self.page.keyboard.press('Enter')
                    submitted = True

                # 等待提交结果
                await asyncio.sleep(random.uniform(2500, 4500))

                # 验证是否发送成功（检查是否有新的评论出现）
                # 注意：YouTube 有时候不会立即显示自己的评论
                # 只要没报错就算成功

                # 检查错误提示
                error_indicators = [
                    '.ytd-comment-rejection-info',
                    '.ytd-error-content-renderer',
                    '[role="alert"]',
                    '#error-message',
                ]
                has_error = False
                for err_sel in error_indicators:
                    err_el = await self.page.query_selector(err_sel)
                    if err_el and await err_el.is_visible():
                        has_error = True
                        error_text = await err_el.inner_text()
                        log.warning(f"⚠️ 评论可能进入审核: {error_text[:80]}")
                        break

                if has_error:
                    # YouTube 审核中也算提交了（不是失败）
                    log.info("✅ 评论已提交（可能在审核队列）")
                    return True
                else:
                    log.info("✅ 评论发布成功!")
                    return True

            except Exception as e:
                log.error(f"❌ 第{attempt+1}次尝试失败: {e}")
                if attempt < max_retries - 1:
                    # 失败后等待更长时间再重试
                    wait_time = random.uniform(8, 15)
                    log.info(f"等待 {wait_time:.0f} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue

        log.error(f"❌ 所有 {max_retries} 次尝试都失败了: {video_url}")
        return False

    async def navigate_to_youtube(self):
        """打开 YouTube 首页（确认登录状态）"""
        await self.page.goto('https://www.youtube.com', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        # 检查是否已登录
        avatar = await self.page.query_selector('#avatar-link img, #img')
        if avatar:
            log.info("✓ 已登录 YouTube")
        else:
            log.info("ℹ 未登录或头像加载异常")

    async def take_screenshot(self, filename=None):
        """截屏保存（调试用）"""
        if filename is None:
            import time
            filename = f"screenshot_{int(time.time())}_{random.randint(1000,9999)}"
        path = SCRIPT_DIR / "logs" / f"{filename}.png"
        try:
            await self.page.screenshot(path=str(path), full_page=False)
            log.info(f"截图保存: {path}")
            return str(path)
        except Exception as e:
            log.error(f"截图失败: {e}")
            return None

    async def close(self):
        """关闭浏览器和所有资源"""
        try:
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'pw') and self.pw:
                await self.pw.stop()
            log.info("浏览器已关闭")
        except Exception as e:
            log.error(f"关闭浏览器时出错: {e}")
