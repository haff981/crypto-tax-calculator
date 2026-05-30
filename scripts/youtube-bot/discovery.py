# ============================================================
#  discovery.py — 视频发现模块
#  功能：通过 YouTube Data API 搜索目标频道最新视频
# ============================================================

import json
import time
import random
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


class VideoDiscovery:
    """YouTube 视频 — 发现器"""

    def __init__(self, api_key=None):
        """
        初始化
        api_key: YouTube Data API v3 Key（免费申请）
                 如果不提供，将使用备用搜索方法
        """
        self.api_key = api_key

    def get_channel_id_from_handle(self, handle):
        """通过 @handle 获取 channel ID"""
        if not self.api_key:
            log.warning("没有 API key，无法查询 channel ID")
            return None

        try:
            params = {
                'part': 'snippet',
                'forHandle': handle,
                'key': self.api_key,
            }
            url = f"https://www.googleapis.com/youtube/v3/channels?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; YouTubeBot/1.0)'
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())

            items = data.get('items', [])
            if items:
                ch_id = items[0]['id']
                log.info(f"✓ Handle @{handle} → Channel ID: {ch_id}")
                return ch_id
            else:
                log.warning(f"未找到 @{handle} 的 channel ID")
                return None
        except Exception as e:
            log.error(f"查询 @{handle} 失败: {e}")
            return None

    def get_latest_videos(self, channel_ids, max_results_per_channel=3,
                          published_after=None):
        """
        获取目标频道的最新视频列表

        参数:
            channel_ids: 频道ID列表 ['UCxxx', 'UCyyy']
            max_results_per_channel: 每个频道最多获取几个视频
            published_after: ISO格式时间，只返回此时间之后发布的视频（如 '2026-05-30T00:00:00Z'）

        返回:
            视频信息字典列表:
            [{
                'video_id': 'xxxxxxxx',
                'title': '视频标题',
                'channel_title': '频道名',
                'channel_id': 'UCxxxxx',
                'published_at': '2026-05-30T12:00:00Z',
                'description': '描述前200字符',
                'url': 'https://youtube.com/watch?v=xxxx',
                'thumbnail': '缩略图URL',
            }, ...]
        """
        videos = []

        for channel_id in channel_ids:
            try:
                # 方法1：使用 YouTube Search API（如果可用）
                if self.api_key:
                    channel_videos = self._search_api(channel_id,
                                                     max_results_per_channel,
                                                     published_after)
                    videos.extend(channel_videos)
                else:
                    # 方法2：无API key时使用网页抓取
                    channel_videos = self._scrape_channel(channel_id,
                                                          max_results_per_channel)
                    videos.extend(channel_videos)

                # 随机延迟避免请求过快
                delay = random.uniform(1.5, 4.0)
                time.sleep(delay)

            except Exception as e:
                log.error(f"获取频道 {channel_id[:15]}... 失败: {e}")
                continue

        log.info(f"📺 共找到 {len(videos)} 个视频")
        return videos

    def _search_api(self, channel_id, max_results, published_after):
        """使用 YouTube Data API 搜索视频"""
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'maxResults': max_results,
            'order': 'date',          # 最新优先
            'type': 'video',         # 只要视频
            'key': self.api_key,
        }
        if published_after:
            params['publishedAfter'] = published_after

        url = f"https://www.googleapis.com/youtube/v3/search?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; YouTubeBot/1.0)',
            'Accept': 'application/json',
        })

        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())

        items = data.get('items', [])
        videos = []
        for item in items:
            snippet = item.get('snippet', {})
            video_id = item.get('id', {}).get('videoId', '')

            if not video_id:
                continue

            videos.append({
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'channel_id': channel_id,
                'published_at': snippet.get('publishedAt', ''),
                'description': snippet.get('description', '')[:300],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            })

        log.info(f"  📌 频道 ...{channel_id[-8:]} → {len(videos)} 个新视频 (API)")
        return videos

    def _scrape_channel(self, channel_id, max_results):
        """
        无 API key 时使用网页抓取获取频道最新视频
        通过 YouTube 频道页面 @videos tab 获取
        """
        import re
        videos = []

        try:
            # 尝试多种频道 URL 格式
            urls_to_try = [
                f"https://www.youtube.com/channel/{channel_id}/videos",
                f"https://www.youtube.com/@{channel_id}/videos",
            ]

            content = None
            for url in urls_to_try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': random.choice([
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
                    ])
                })
                try:
                    resp = urllib.request.urlopen(req, timeout=15)
                    content = resp.read().decode('utf-8', errors='ignore')
                    break
                except:
                    continue

            if not content:
                log.warning(f"  ⚠ 无法抓取频道页面: {channel_id}")
                return []

            # 用正则提取视频信息
            # YouTube 页面中包含 ytInitialData 或 videoId 模式
            patterns = [
                r'"videoId":"([^"]+)"[^}]*?"title":\s*"?([^"\\]+)"?',
                r'/watch\?v=([a-zA-Z0-9_-]{11})',
            ]

            found_video_ids = set()

            # 尝试从 JSON 数据块提取
            json_match = re.search(r'var ytInitialData\s*=\s*(\{.+?\});', content, re.DOTALL)
            if json_match:
                try:
                    raw_data = json_match.group(1)
                    data = json.loads(raw_data)

                    # 遍历 JSON 找到视频列表
                    raw_str = json.dumps(data)

                    # 提取所有 videoId
                    all_ids = re.findall(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', raw_str)

                    # 提取所有标题（紧邻 videoId 的 title）
                    titles_raw = re.findall(r'"title"\s*:\s*\{"runs":\s*\[\{"text"\s*:\s*"([^"]+)"', raw_str)
                    if not titles_raw:
                        titles_raw = re.findall(r'"title"\s*:\s*"([^"]{10,200})"', raw_str)

                    for i, vid in enumerate(all_ids):
                        if vid in found_video_ids or len(found_video_ids) >= max_results:
                            break
                        found_video_ids.add(vid)
                        title = titles_raw[i] if i < len(titles_raw) else f"Video #{i+1}"

                        videos.append({
                            'video_id': vid,
                            'title': title,
                            'channel_title': '',
                            'channel_id': channel_id,
                            'published_at': '',
                            'description': '',
                            'url': f"https://www.youtube.com/watch?v={vid}",
                            'thumbnail': f"https://img.youtube.com/vi{vid}/hqdefault.jpg",
                        })

                except json.JSONDecodeError:
                    pass

            # Fallback: 如果 JSON 解析失败，用简单正则
            if not videos and patterns:
                ids_found = re.findall(patterns[1], content)
                for vid in ids_found:
                    if vid in found_video_ids or len(found_video_ids) >= max_results:
                        break
                    found_video_ids.add(vid)
                    videos.append({
                        'video_id': vid,
                        'title': '',
                        'channel_title': '',
                        'channel_id': channel_id,
                        'published_at': '',
                        'description': '',
                        'url': f"https://www.youtube.com/watch?v={vid}",
                        'thumbnail': f"https://img.youtube.com/vi{vid}/hqdefault.jpg",
                    })

            log.info(f"  📌 频道 ...{channel_id[-8:]} → {len(videos)} 个视频 (scrape)")
            return videos

        except Exception as e:
            log.error(f"  ❌ 网页抓取失败 ({channel_id}): {e}")
            return []

    def get_trending_crypto_videos(self, query="crypto", max_results=10):
        """
        搜索热门 crypto 相关视频（备用方法，用于发现新的引流目标）
        不需要 API key，使用 YouTube 搜索页面
        """
        import re
        videos = []

        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=CAMSAhAB"

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
            })

            resp = urllib.request.urlopen(req, timeout=15)
            content = resp.read().decode('utf-8', errors='ignore')

            # 提取视频ID和标题
            ids = set(re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', content))

            for vid in list(ids)[:max_results]:
                videos.append({
                    'video_id': vid,
                    'title': '',
                    'channel_title': '',
                    'channel_id': '',
                    'published_at': '',
                    'description': '',
                    'url': f"https://www.youtube.com/watch?v={vid}",
                    'thumbnail': f"https://img.youtube.com/vi{vid}/hqdefault.jpg",
                })

            log.info(f"🔥 搜索 '{query}' 找到 {len(videos)} 个热门视频")
            return videos

        except Exception as e:
            log.error(f"搜索失败: {e}")
            return []
