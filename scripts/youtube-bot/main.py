# ============================================================
#  main.py — YouTube 自动评论机器人 主程序
#  
#  使用方法:
#    python main.py                     # 运行一次
#    python main.py --loop              # 持续循环
#    python main.py --loop --interval 30   # 每30分钟检查一次
#    python main.py --dry-run           # 试运行（只搜索不发送）
#    python main.py --test-login        # 只测试登录
#
#  托管运行:
#    nohup python main.py --loop > bot.log 2>&1 &
#    或使用 systemd 服务
# ============================================================

import json
import os
import sys
import time
import random
import logging
import argparse
import asyncio
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 确保项目目录在 sys.path 中
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 目录定义
DATA_DIR = SCRIPT_DIR / "data"
LOG_DIR = SCRIPT_DIR / "logs"
STATE_FILE = DATA_DIR / "state.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 日志配置
def setup_logging():
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    # 文件日志（每天一个文件）
    today_str = datetime.date.today().isoformat()
    log_file = LOG_DIR / f"bot_{today_str}.log"

    handlers = [
        logging.FileHandler(log_file, encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=datefmt,
        handlers=handlers,
        force=True,  # 覆盖已有配置
    )

setup_logging()
log = logging.getLogger(__name__)


# ============================================================
#  配置管理
# ============================================================

def load_config():
    """加载配置文件"""
    config_file = SCRIPT_DIR / "config.json"

    if not config_file.exists():
        log.error(f"❌ 配置文件不存在: {config_file}")
        log.info("请复制 config.json 并填写账号和频道信息")
        sys.exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 设置默认值
    config.setdefault('max_comments_per_run', 5)
    config.setdefault('comments_before_switch', 3)
    config.setdefault('check_interval_minutes', 30)
    config.setdefault('daily_limit_per_account', 15)
    config.setdefault('headless', True)
    config.setdefault('active_hours_start', 9)
    config.setdefault('active_hours_end', 24)
    config.setdefault('timezone', 'America/New_York')
    config.setdefault('promo_link',
                    'https://haff981.github.io/crypto-tax-calculator/')
    config.setdefault('youtube_api_key', None)

    # 验证关键配置
    if not config.get('accounts'):
        log.error("❌ config.json 中没有配置 accounts")
        sys.exit(1)
    if not config.get('target_channels'):
        log.error("❌ config.json 中没有配置 target_channels")
        sys.exit(1)

    return config


def load_state():
    """加载状态文件"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            # 确保所有必要字段存在
            state.setdefault('commented_videos', [])
            state.setdefault('last_check_time', None)
            state.setdefault('total_comments', 0)
            state.setdefault('account_usage', {})
            state.setdefault('errors', [])
            state.setdefault('today_count', {})
            state.setdefault('daily_reset_date', '')
            return state
        except (json.JSONDecodeError, Exception) as e:
            log.warning(f"状态文件读取失败，重新初始化: {e}")

    return {
        'commented_videos': [],
        'last_check_time': None,
        'total_comments': 0,
        'account_usage': {},
        'errors': [],
        'today_count': {},
        'daily_reset_date': '',
    }


def save_state(state):
    """保存状态到文件"""
    try:
        # 限制 errors 数组大小，防止无限增长
        if len(state['errors']) > 100:
            state['errors'] = state['errors'][-50:]

        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"保存状态失败: {e}")


def reset_daily_counts(state):
    """重置每日计数器（如果日期变了）"""
    today = datetime.date.today().isoformat()
    if state.get('daily_reset_date') != today:
        state['today_count'] = {}
        state['daily_reset_date'] = today
        log.info(f"📅 新的一天 ({today}) — 每日计数器已重置")


# ============================================================
#  时间检查
# ============================================================

def is_active_hour(config):
    """检查当前是否在活跃时段内"""
    try:
        tz_name = config.get('timezone', 'America/New_York')
        tz = ZoneInfo(tz_name)
        now_local = datetime.datetime.now(tz)
        current_hour = now_local.hour

        start = config.get('active_hours_start', 9)
        end = config.get('active_hours_end', 24)

        is_active = start <= current_hour < end
        if not is_active:
            log.info(f"⏰ 非活跃时段 ({tz_name} {current_hour}:00 "
                     f"不在 {start:02d}:00-{end:02d}:00 内)，跳过")

        return is_active
    except Exception as e:
        log.warning(f"时区检查失败: {e}")
        return True  # 出错时不阻塞


# ============================================================
#  核心逻辑：一轮执行
# ============================================================

async def run_once(config, state):
    """
    执行一轮：发现新视频 → 匹配文案 → 发评论 → 更新状态
    返回: (success_count, fail_count) 元组
    """

    # 导入模块
    from browser import YouTubeCommenter
    from discovery import VideoDiscovery
    from comment import CommentGenerator

    commenter = YouTubeCommenter(headless=config.get('headless', True))
    discovery = VideoDiscovery(api_key=config.get('youtube_api_key'))

    accounts = config.get('accounts', [])
    channels = config.get('target_channels', [])
    generator = CommentGenerator(link=config.get('promo_link'))
    channel_ids = [ch['channel_id'] for ch in channels]

    max_per_run = config.get('max_comments_per_run', 5)
    switch_every = config.get('comments_before_switch', 3)
    daily_limit = config.get('daily_limit_per_account', 15)
    
    # 选择起始账号（轮换）
    start_idx = state['total_comments'] % len(accounts) if accounts else 0
    current_idx = start_idx

    success_count = 0
    fail_count = 0

    try:
        # 初始化浏览器 + 登录
        account_info = accounts[current_idx]
        await commenter.init_browser(account_info=account_info)

        # 先打开 YouTube 确认登录状态
        await commenter.navigate_to_youtube()

        # 发现最新视频
        log.info("=" * 55)
        log.info("🔍 搜索目标频道的最新视频...")
        
        last_check = state.get('last_check_time')
        videos = discovery.get_latest_videos(
            channel_ids=channel_ids,
            max_results_per_channel=config.get('max_videos_per_channel', 3),
            published_after=last_check
        )

        # 过滤已评论过的视频
        commented_set = set(state.get('commented_videos', []))
        new_videos = [v for v in videos if v['video_id'] not in commented_set]

        log.info(f"📊 总计 {len(videos)} 个视频 | "
                 f"其中 {len(new_videos)} 个待评论")

        if not new_videos:
            log.info("✅ 没有需要评论的新视频")
            return (0, 0)

        # 打乱顺序（看起来更自然）
        random.shuffle(new_videos)

        # 限制本轮最多评论数
        videos_to_comment = new_videos[:max_per_run]

        log.info(f"🎯 本轮计划评论 {len(videos_to_comment)} 条")

        # 逐个发评论
        for i, video in enumerate(videos_to_comment):

            # 检查今日限额
            reset_daily_counts(state)
            acc_key = str(current_idx)
            today_used = state['today_count'].get(acc_key, 0)
            if today_used >= daily_limit:
                log.warning(f"⚠️ 账号 #{current_idx+1} 今日已用 "
                           f"{today_used}/{daily_limit}，切换下一个")
                if len(accounts) > 1:
                    current_idx = (current_idx + 1) % len(accounts)
                    account_info = accounts[current_idx]
                    await commenter.close()
                    await asyncio.sleep(random.uniform(3, 6))
                    await commenter.init_browser(account_info=account_info)
                else:
                    log.info("所有账号已达日限，暂停本轮")
                    break

            try:
                log.info("")
                log.info(f"--- 评论 #{i+1}/{len(videos_to_comment)} ---")
                log.info(f"  📺 {video.get('title', '(无标题)')[:60]}")
                log.info(f"  📡 {video.get('channel_title', '')}")
                log.info(f"  🔗 {video.get('url', '')}")

                # 生成评论文案
                comment_text = generator.generate(video)
                log.info(f"  💬 文案: {comment_text[:80]}...")

                # 发表评论
                success = await commenter.post_comment(
                    video['url'],
                    comment_text,
                    max_retries=2  # 每条视频最多重试2次
                )

                if success:
                    state['commented_videos'].append(video['video_id'])
                    state['total_comments'] += 1
                    state['account_usage'][str(current_idx)] = \
                        state['account_usage'].get(str(current_idx), 0) + 1
                    state['today_count'][acc_key] = \
                        state['today_count'].get(acc_key, 0) + 1
                    success_count += 1
                    log.info(f"  ✅ 成功! (总计 {state['total_comments']} 条)")
                else:
                    fail_count += 1
                    log.warning(f"  ❌ 失败")

                # 随机延迟（模拟真人行为）
                interval = random.uniform(60, 180)
                log.info(f"  ⏳ 等待 {interval:.0f}s...")
                await asyncio.sleep(interval)

                # 每发 N 条切换一次账号
                if (i + 1) % switch_every == 0 and len(accounts) > 1:
                    next_idx = (current_idx + 1) % len(accounts)
                    log.info(f"🔄 切换到账号 #{next_idx + 1}")
                    await commenter.close()
                    await asyncio.sleep(random.uniform(4, 8))
                    await commenter.init_browser(account_info=accounts[next_idx])
                    current_idx = next_idx

            except Exception as e:
                fail_count += 1
                log.error(f"  ❌ 处理视频出错: {e}")
                state['errors'].append({
                    'time': datetime.datetime.now().isoformat(),
                    'video_id': video.get('video_id'),
                    'error': str(e)[:200],
                })
                continue

        # 更新最后检查时间
        state['last_check_time'] = datetime.datetime.now(
            datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    except KeyboardInterrupt:
        log.info("\n⛔ 用户中断")
    except Exception as e:
        log.error(f"💥 主程序异常: {e}")
        import traceback
        traceback.print_exc()
        state['errors'].append({
            'time': datetime.datetime.now().isoformat(),
            'error': f"主程序异常: {str(e)[:200]}"
        })
        fail_count += 1

    finally:
        await commenter.close()

    # 保存状态
    save_state(state)

    # 输出本轮统计
    log.info("")
    log.info("=" * 55)
    log.info(f"📋 本轮完成: ✅{success_count} 成功 | ❌{fail_count} 失败")
    log.info(f"📊 历史累计: {state['total_comments']} 条评论")
    log.info(f"👤 账号使用次数: {state['account_usage']}")
    if state.get('today_count'):
        log.info(f"📅 今日各账号: {state['today_count']}")

    return (success_count, fail_count)


# ============================================================
#  测试模式
# ============================================================

async def test_login(config):
    """测试登录功能"""
    from browser import YouTubeCommenter

    accounts = config.get('accounts', [])
    if not accounts:
        log.error("没有可用的账号")
        return

    commenter = YouTubeCommenter(headless=False)  # 有头模式方便看
    account = accounts[0]

    log.info("=" * 55)
    log.info("🧪 测试登录模式（会打开浏览器窗口）")
    log.info(f"   账号: {account.get('email')}")
    log.info("=" * 55)

    try:
        await commenter.init_browser(account_info=account)
        await commenter.navigate_to_youtube()

        screenshot_path = await commenter.take_screenshot("test_login")
        log.info(f"✅ 登录测试完成! 截图: {screenshot_path}")

        # 保持浏览器打开让用户检查
        log.info("浏览器将在 30 秒后关闭...")
        await asyncio.sleep(30)

    finally:
        await commenter.close()


async def dry_run(config, state):
    """试运行：只搜索视频不发送评论"""
    from discovery import VideoDiscovery
    from comment import CommentGenerator

    discovery = VideoDiscovery(api_key=config.get('youtube_api_key'))
    generator = CommentGenerator(link=config.get('promo_link'))
    channels = config.get('target_channels', [])
    discovery._channel_infos = channels  # 传handle信息（必须在channels定义之后）

    log.info("=" * 55)
    log.info("🔍 试运行模式 — 只搜索不发送评论")
    log.info("=" * 55)

    videos = discovery.get_latest_videos(
        channel_ids=[ch['channel_id'] for ch in channels],
        max_results_per_channel=3,
    )

    commented_set = set(state.get('commented_videos', []))
    new_videos = [v for v in videos if v['video_id'] not in commented_set]

    log.info(f"\n找到 {len(videos)} 个视频, 其中 {len(new_videos)} 个未评论:\n")

    for i, v in enumerate(new_videos[:10], 1):
        comment = generator.generate(v)
        print(f"\n{'─' * 50}")
        print(f"  #{i} [{v.get('channel_title','?')}]")
        print(f"  标题: {v.get('title', '(无)')[:70]}")
        print(f"  链接: {v.get('url', '')}")
        print(f"  发布: {v.get('published_at', '?')[:16]}")
        print(f"  生成评论: {comment[:120]}...")

    log.info(f"\n✅ 试运行完成 — 共 {len(new_videos)} 条待评论")
    return len(new_videos)


# ============================================================
#  主程序入口
# ============================================================

async def main():
    parser = argparse.ArgumentParser(
        description='YouTube 自动评论推广机器人 — Crypto Tax Calculator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --test-login     # 测试登录
  python main.py --dry-run       # 试运行（不发送）
  python main.py --loop          # 循环运行
  python main.py --loop --interval 60  # 每60分钟检查
        """)
    parser.add_argument('--loop', action='store_true',
                        help='持续循环模式')
    parser.add_argument('--interval', type=int, default=30,
                        help='循环间隔（分钟），默认30')
    parser.add_argument('--dry-run', action='store_true',
                        help='试运行模式（只搜索不发送评论）')
    parser.add_argument('--test-login', action='store_true',
                        help='只测试登录功能（会弹窗）')
    parser.add_argument('--headless-off', action='store_true',
                        help='显示浏览器窗口（调试用）')

    args = parser.parse_args()

    # 加载配置
    config = load_config()
    state = load_state()

    # 显示启动信息
    log.info("")
    log.info("╔════════════════════════════════════════════╗")
    log.info("║  🤖 YouTube Auto-Comment Bot v1.0          ║")
    log.info("╠════════════════════════════════════════════╣")
    log.info(f"║  目标频道: {len(config.get('target_channels', [])):<32}║")
    log.info(f"║  可用账号: {len(config.get('accounts', [])):<32}║")
    log.info(f"║  文案模板: 42+ 条                          ║")
    log.info(f"║  推广链接: {config.get('promo_link', '')[:35]:<35}║")
    log.info(f"║  历史评论: {state.get('total_comments', 0):<32}║")
    log.info(f"║  已评论视频: {len(state.get('commented_videos', [])):<28}║")
    log.info("╚════════════════════════════════════════════╝")
    log.info("")

    # 测试登录模式
    if args.test_login:
        await test_login(config)
        return

    # 试运行模式
    if args.dry_run:
        await dry_run(config, state)
        return

    # 关闭 headless（调试用）
    if args.headless_off:
        config['headless'] = False

    # 单次运行或循环运行
    if args.loop:
        log.info(f"🔄 循环模式启动 — 每 {args.interval} 分钟检查一次\n")

        consecutive_failures = 0
        max_consecutive_failures = 5

        while True:
            try:
                # 检查是否在活跃时段
                if not is_active_hour(config):
                    wait_min = 10
                    log.info(f"等待 {wait_min} 分钟后重试...")
                    await asyncio.sleep(wait_min * 60)
                    continue

                # 执行一轮
                ok, fail = await run_once(config, state)

                if fail > 0 and ok == 0:
                    consecutive_failures += 1
                    log.warning(f"⚠️ 连续失败 {consecutive_failures}/{max_consecutive_failures}")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        log.error("❌ 连续失败次数过多，暂停 2 小时")
                        await asyncio.sleep(7200)
                        consecutive_failures = 0
                else:
                    consecutive_failures = 0

                # 等待下一轮
                interval_sec = args.interval * 60
                jitter = random.randint(-300, 300)  # ±5分钟随机偏移
                actual_wait = interval_sec + jitter
                
                next_time = datetime.datetime.now() + datetime.timedelta(seconds=actual_wait)
                log.info(f"\n⏰ 下次检查时间: {next_time.strftime('%H:%M:%S')} "
                         f"(约 {actual_wait//60} 分钟后)\n")
                
                await asyncio.sleep(actual_wait)

            except KeyboardInterrupt:
                log.info("\n🛑 用户手动停止")
                break
            except Exception as e:
                log.error(f"循环异常: {e}")
                await asyncio.sleep(120)  # 出错等 2 分钟再继续
    else:
        # 单次运行
        # 检查活跃时段
        if not is_active_hour(config):
            log.info("当前非活跃时段。如要强制运行请去掉时段限制或使用 --loop 模式")
            return

        await run_once(config, state)


if __name__ == '__main__':
    asyncio.run(main())
