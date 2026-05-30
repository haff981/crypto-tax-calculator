# ============================================================
#  comment.py - Comment Template Generator
#  Auto-matches best template based on video content
# ============================================================

import random
import logging

log = logging.getLogger(__name__)


class CommentGenerator:
    """Smart comment generator with category matching + randomization"""

    TEMPLATES = [
        # === MEME COIN ===
        {'category': 'meme',
         'text': 'Those gains look insane but do not forget Uncle Sam wants up to 37% of short-term crypto profits {EMOJI} I built a free tool to calculate what you ACTUALLY keep after tax {LINK}'},
        {'category': 'meme',
         'text': 'Made a nice bag on this one but after cap gains tax I kept way less than I thought {EMOJI} Check your actual after-tax profit here (free): {LINK}'},
        {'category': 'meme',
         'text': 'Meme coin season is here but how many of you are actually TRACKING your tax liability? Most people find out in April and it is not fun {LINK}'},
        {'category': 'meme',
         'text': 'If you are trading memecoins and not calculating your tax position, you are playing on hard mode. This does the math for free: {LINK}'},
        {'category': 'meme',
         'text': '{CHANNEL} knows what is up with meme plays! Just remember those 50x gains get hit with up to 37% short-term cap gains tax {EMOJI} Calculate yours: {LINK}'},
        {'category': 'meme',
         'text': 'Everyone celebrating their meme coin bags right now {EMOJI} Real question though - have you calculated your actual tax liability? Free tool: {LINK}'},

        # === AIRDROP ===
        {'category': 'airdrop',
         'text': 'Free money? Not exactly... The IRS counts airdrops as ordinary income (up to 37% federal). Calculate yours before it is too late {EMOJI} {LINK}'},
        {'category': 'airdrop',
         'text': 'If you are farming airdrops in 2026, you NEED to know this: that "free" token drop = taxable income event. Built a free calculator just for this: {LINK}'},
        {'category': 'airdrop',
         'text': 'Airdrops are the best thing in crypto but the worst thing at tax time {EMOJI} Do not let the IRS surprise you. Free calc: {LINK}'},
        {'category': 'airdrop',
         'text': 'Great alpha on airdrops here! One tip from someone who learned the hard way - track your cost basis from day one or April will hurt {LINK}'},
        {'category': 'airdrop',
         'text': 'Just realized I owed way more in taxes on my airdrops than I thought {EMOJI} Made this free tool so you do not make the same mistake: {LINK}'},
        {'category': 'airdrop',
         'text': 'For everyone farming airdrops watching this - do not forget the TAX on those "free" tokens {EMOJI} It counts as ordinary income up to 37%. Check yours: {LINK}'},

        # === PROFIT / GAINS ===
        {'category': 'profit',
         'text': 'Real talk - how much of that profit are you keeping after taxes? Short-term crypto gains = regular income rate (up to 37%). Check what you actually owe (free): {LINK}'},
        {'category': 'profit',
         'text': 'Nice gains {EMOJI} But do not forget Uncle Sam cut. If you held less than a year, that is short-term cap gains at your income bracket. Free calculator: {LINK}'},
        {'category': 'profit',
         'text': 'These kinds of gains are why you need to track your taxes from day 1. Do not be the person panicking in April {EMOJI} Free tool: {LINK}'},
        {'category': 'profit',
         'text': 'Hot take: most crypto traders underestimate their tax bill by 40%+ because they forget about short-term capital gains rates. Do not be most traders: {LINK}'},
        {'category': 'profit',
         'text': 'Big moves like this = big tax bill if you are not planning ahead. Know your numbers before you sell {EMOJI} {LINK}'},

        # === TAX RELATED ===
        {'category': 'tax',
         'text': 'TurboTax crypto import is trash for airdrops and meme coins {EMOJI} Been using this free alternative instead, handles both scenarios properly: {LINK}'},
        {'category': 'tax',
         'text': 'If you are still manually calculating your crypto tax in a spreadsheet... stop. This does it in seconds and covers edge cases most tools miss: {LINK}'},
        {'category': 'tax',
         'text': 'The IRS is getting more aggressive about crypto tax enforcement every year. Do not get caught unprepared. Free calculator: {LINK}'},
        {'category': 'tax',
         'text': 'Crypto taxes are not that complicated if you use the right tools {EMOJI} Airdrops, meme coins, DeFi yields - this covers all of it for free: {LINK}'},

        # === DeFi / YIELD FARMING ===
        {'category': 'defi',
         'text': 'Those APYs look amazing but the tax bill on staking/farming rewards hits different {EMOJI} Ordinary income tax applies. Plan ahead: {LINK}'},
        {'category': 'defi',
         'text': 'DeFi yields are sexy until you realize staking rewards = ordinary income (up to 37%). Farm smart, know your tax: {LINK}'},
        {'category': 'defi',
         'text': 'Great breakdown of DeFi strategies! Quick reminder: all those yield farming rewards are taxable events. Track them from day 1: {LINK}'},
        {'category': 'defi',
         'text': 'Yield farming is literally the best thing in crypto AND the worst thing at tax season if you did not track everything {EMOJI} Use this: {LINK}'},
        {'category': 'defi',
         'text': '{CHANNEL} always drops solid DeFi alpha! For anyone following these plays - set aside ~30% for taxes on those farming rewards {LINK}'},

        # === BTC/ETH / PRICE ACTION ===
        {'category': 'btc_eth',
         'text': 'Bull run incoming {EMOJI} But smart traders calculate their tax exposure NOW instead of panicking in April. Free crypto tax calc: {LINK}'},
        {'category': 'btc_eth',
         'text': 'Price going up is great until you realize your short-term capital gains tax rate {EMOJI} If you have been DCAing, figure out your actual gain + tax here: {LINK}'},
        {'category': 'btc_eth',
         'text': 'Everyone bullish on price but bearish on their future tax bill {EMOJI} Every crypto holder should know their current tax position. Free: {LINK}'},
        {'category': 'btc_eth',
         'text': 'Great TA! One thing people forget during bull runs - every trade you close triggers a taxable event. Know your running total: {LINK}'},

        # === TUTORIAL / BEGINNER ===
        {'category': 'tutorial',
         'text': 'Awesome tutorial! Quick tip for anyone starting out - track your tax liability from Day 1 so you do not get wrecked in April {EMOJI} Free calculator: {LINK}'},
        {'category': 'tutorial',
         'text': 'This is gold for beginners! Also if you are putting real money into any of this, check your tax exposure. A lot of people learn the hard way {LINK}'},
        {'category': 'tutorial',
         'text': 'Solid guide for newcomers {EMOJI} Pro tip: download your trade history monthly. Future you will thank present you when tax season comes. Or just use this: {LINK}'},
        {'category': 'tutorial',
         'text': 'Great tutorial! Once you start making real money in crypto, tax tracking becomes mandatory not optional {EMOJI} Here is a free tool that makes it easy: {LINK}'},

        # === GENERIC (any crypto video) ===
        {'category': 'generic',
         'text': 'If you are making money in crypto and NOT tracking your tax liability, you are gonna have a bad time in April {EMOJI} {LINK}'},
        {'category': 'generic',
         'text': 'PSA for anyone in crypto: the IRS does not care that you "did not know" about crypto taxes. Calculate yours now for free: {LINK}'},
        {'category': 'generic',
         'text': 'Just found this free crypto tax calculator and it actually handles airdrops properly (which most $200/year tools do not) {EMOJI} {LINK}'},
        {'category': 'generic',
         'text': 'Crypto tax tools either cost $200+/year or suck at handling airdrops and meme coins. So I built a free one that does not {EMOJI} {LINK}'},
        {'category': 'generic',
         'text': '3 calculators in one tool. Meme coins, airdrops, capital gains. US tax rates. Completely free tier. Takes 30 seconds: {LINK}'},
        {'category': 'generic',
         'text': 'Built for degens by degens {EMOJI} Free crypto tax calculator that actually understands airdrops and meme coins. Not trying to replace TurboTax - just want every degen to know what they owe: {LINK}'},
        {'category': 'generic',
         'text': 'Your airdrops are not free money. That $5k drop? Could mean $1,850 in taxes (37% bracket) plus cap gains when you sell. Know your numbers: {LINK}'},
        {'category': 'generic',
         'text': 'Most crypto tax calculators are built by people who do not actually trade crypto. This one is different {EMOJI} Covers airdrops, meme coins, DeFi yields: {LINK}'},
    ]

    def __init__(self, templates=None, link=None):
        self.templates = templates or self.TEMPLATES.copy()
        self.link = link or "https://haff981.github.io/crypto-tax-calculator/"
        self.emojis = ['\U0001f525', '\U0001f680', '\U0001f4b0', '\U0001f4ca', '\U0001f9e0', '\U0001f4a9', '\U0001f91d', '\U0001f44c', '\U0001f4af', '\U0001f680', '\U0001f4e6', '\U0001f929', '\U0001f3af']
        self.recently_used = []

    def generate(self, video_info, force_category=None):
        title = video_info.get('title', '').lower()
        desc = video_info.get('description', '').lower()
        channel = video_info.get('channel_title', '')

        if force_category:
            category = force_category
        else:
            category = self._detect_category(title, desc)

        candidates = [i for i, t in enumerate(self.templates)
                      if t.get('category') == category]

        if not candidates:
            candidates = [i for i, t in enumerate(self.templates)
                          if t.get('category') == 'generic']
        if not candidates:
            candidates = list(range(len(self.templates)))

        available = [idx for idx in candidates
                    if idx not in self.recently_used[-6:]]

        if not available:
            available = candidates
            self.recently_used.clear()

        selected_idx = random.choice(available)
        self.recently_used.append(selected_idx)
        template_text = self.templates[selected_idx]['text']

        comment = template_text.replace('{CHANNEL}', channel)
        comment = comment.replace('{TITLE}',
                                  (video_info.get('title', ''))[:60])

        if '{EMOJI}' in comment:
            comment = comment.replace('{EMOJI}', random.choice(self.emojis))

        if '{LINK}' in comment:
            if random.random() < 0.7:
                emoji_prefix = random.choice(['\U0001f525', '', '\U0001f680'])
                link_str = f"{emoji_prefix} {self.link}" if emoji_prefix else self.link
            else:
                link_str = self.link
            comment = comment.replace('{LINK}', link_str)

        comment = ' '.join(comment.split())
        log.info(f"[{category}] ({selected_idx}): {comment[:70]}...")
        return comment

    def _detect_category(self, title, description):
        text = f"{title} {description}"
        rules = [
            ('meme', ['meme', 'pepe', 'doge', 'bonk', 'wif', 'shib',
                      'floki', 'memecoin', 'pump fun']),
            ('airdrop', ['airdrop', 'air drop', 'free token', 'free crypto',
                        'token distribution', 'claim']),
            ('profit', ['profit', 'gain', 'pump', 'moon', 'x10', 'x100',
                       'x1000', 'made money', 'bag', 'portfolio up', 'winning',
                       'gains']),
            ('tax', ['tax', 'irs', 'capital gain', 'reporting', 'filing',
                    'taxable', 'deduction']),
            ('defi', ['defi', 'yield', 'staking', 'farm', 'apy', 'lending',
                     'liquidity', 'lp', 'vault', 'pool', 'rewards', 'compound']),
            ('btc_eth', ['bitcoin', 'ethereum', 'eth', 'btc', 'solana',
                        'sol', 'price up', 'bull run', 'ath', 'market pump',
                        'green candle']),
            ('tutorial', ['tutorial', 'how to', 'guide', 'beginner',
                         'getting started', 'intro', 'explained', 'for dummies']),
        ]
        scores = {}
        for cat, keywords in rules:
            score = sum(1 for kw in keywords if kw.lower() in text.lower())
            if score > 0:
                scores[cat] = score
        return max(scores, key=scores.get) if scores else 'generic'

    def get_random_generic(self):
        generic = [i for i, t in enumerate(self.templates)
                  if t.get('category') == 'generic']
        idx = random.choice(generic)
        return self.templates[idx]['text'].replace(
            '{EMOJI}', random.choice(self.emojis)).replace(
            '{LINK}', self.link)

    def stats(self):
        cats = {}
        for t in self.templates:
            c = t.get('category')
            cats[c] = cats.get(c, 0) + 1
        return {'total_templates': len(self.templates),
                'categories': cats,
                'link': self.link}
