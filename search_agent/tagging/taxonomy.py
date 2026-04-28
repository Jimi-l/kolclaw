from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from search_agent.config import PACKAGE_ROOT


KOLCLAW_DOC_PATH = PACKAGE_ROOT.parent.parent / "ai_social" / "external_docs" / "operational" / "KolClaw_达人标签_codex.md"


@dataclass(frozen=True)
class ContentRule:
    path: tuple[str, ...]
    keywords: tuple[str, ...]
    negative_keywords: tuple[str, ...] = ()


def _read_kolclaw_doc() -> str:
    try:
        return KOLCLAW_DOC_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _extract_taxonomy_block(doc_text: str) -> str:
    match = re.search(r"### 8\.1 .*?```text\s*(.*?)```", doc_text, flags=re.S)
    return match.group(1) if match else ""


def _parse_content_taxonomy_paths(doc_text: str) -> tuple[tuple[str, ...], ...]:
    block = _extract_taxonomy_block(doc_text)
    paths: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or "->" not in line:
            continue
        segments = [segment.strip() for segment in line.split("->") if segment.strip()]
        if not segments:
            continue
        normalized = tuple(segments[:4])
        if normalized in seen:
            continue
        seen.add(normalized)
        paths.append(normalized)
    return tuple(paths)


def _parse_profile_tag_table(doc_text: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    match = re.search(r"### 9\.1 原始标签表\s*\n\n(.*?)(?:\n---|\Z)", doc_text, flags=re.S)
    block = match.group(1) if match else ""
    profession_tags: list[str] = []
    interest_tags: list[str] = []
    life_tags: list[str] = []
    relation_tags: list[str] = []
    seen_columns: list[set[str]] = [set(), set(), set(), set()]
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "---" in line or "职业标签" in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 4:
            continue
        columns = [profession_tags, interest_tags, life_tags, relation_tags]
        for index, value in enumerate(parts):
            if not value or value in seen_columns[index]:
                continue
            columns[index].append(value)
            seen_columns[index].add(value)
    return tuple(profession_tags), tuple(interest_tags), tuple(life_tags), tuple(relation_tags)


_DOC_TEXT = _read_kolclaw_doc()
CONTENT_TAXONOMY_LINES = _parse_content_taxonomy_paths(_DOC_TEXT)
PROFESSION_TAGS, INTEREST_TAGS, LIFE_TAGS, APPEARANCE_RELATION_TAGS = _parse_profile_tag_table(_DOC_TEXT)


CONTENT_RULES: tuple[ContentRule, ...] = (
    ContentRule(
        path=("影视娱乐", "影视综", "影视解说"),
        keywords=(
            "电影解说",
            "影视解说",
            "深度解析",
            "剧情解析",
            "一口气看完",
            "精讲团",
            "韩剧",
            "美剧",
            "电视剧",
            "纪录片",
            "综艺",
            "抖音精选",
            "第1集",
            "第2集",
            "第3集",
            "第4集",
            "第5集",
            "第6集",
            "第7集",
            "第8集",
            "第9集",
            "第10集",
        ),
    ),
    ContentRule(
        path=("影视娱乐", "短剧剧情", "短剧"),
        keywords=("短剧", "反转", "都市短剧", "乡村短剧", "古风短剧", "情感短剧", "正能量短剧"),
    ),
    ContentRule(
        path=("游戏", "游戏类型", "竞技游戏", "游戏解说"),
        keywords=(
            "游戏解说",
            "游戏攻略",
            "游戏实况",
            "游戏测评",
            "三角洲行动",
            "无畏契约",
            "王者荣耀",
            "和平精英",
            "英雄联盟",
            "吃鸡",
        ),
    ),
    ContentRule(
        path=("3C 数码科技", "科技互联网", "AIGC,AI 整活", "AI 应用"),
        keywords=("aigc", "ai应用", "ai 教程", "ai教程", "提示词", "智能体", "chatgpt", "gemini", "midjourney", "comfyui"),
        negative_keywords=("疑似使用了 ai 生成技术",),
    ),
    ContentRule(
        path=("3C 数码科技", "数码产品", "手机", "手机评测"),
        keywords=("手机评测", "手机测评", "手机开箱", "手机配件", "平板电脑", "耳机评测", "数码开箱", "电子产品测评"),
    ),
    ContentRule(
        path=("文化娱乐", "知识教育", "科普人文", "历史"),
        keywords=("历史", "人文历史", "国学", "传统文化", "地理", "科普人文", "历史故事"),
    ),
    ContentRule(
        path=("文化娱乐", "知识教育", "科普人文", "法律"),
        keywords=("法律", "法考", "律师", "判例", "法条", "普法"),
    ),
    ContentRule(
        path=("美食餐饮", "美食制作", "美食教程"),
        keywords=("美食教程", "做饭", "家常菜", "下饭菜", "菜谱", "烹饪", "早餐美食", "汤品教程", "海鲜烹饪"),
    ),
    ContentRule(
        path=("美食餐饮", "美食探店", "美食探店"),
        keywords=("探店", "餐厅", "咖啡", "奶茶", "外卖测评", "美食之旅", "地方美食"),
    ),
    ContentRule(
        path=("美妆个护", "护肤保养", "面部护肤"),
        keywords=("护肤", "面霜", "精华", "抗老", "祛痘", "防晒", "美白", "修复"),
    ),
    ContentRule(
        path=("美妆个护", "美妆彩妆", "妆教"),
        keywords=("妆教", "妆容", "底妆", "眼妆", "唇妆", "仿妆", "变装造型"),
    ),
    ContentRule(
        path=("服饰穿搭", "穿搭风格", "日常穿搭"),
        keywords=("穿搭", "ootd", "lookbook", "通勤穿搭", "约会穿搭", "辣妹穿搭", "小个子穿搭"),
    ),
    ContentRule(
        path=("出行旅游", "旅游出行", "旅游攻略"),
        keywords=("旅游攻略", "旅行攻略", "景点", "酒店", "自驾游", "露营", "环球旅行", "海外旅行", "国内旅行"),
    ),
    ContentRule(
        path=("汽车", "乘用车", "车型测评"),
        keywords=("汽车", "车评", "试驾", "新能源", "车型对比", "车型测评", "用车知识", "驾驶技巧"),
    ),
    ContentRule(
        path=("财经金融", "财经资讯", "财经资讯"),
        keywords=("财经", "股票", "基金", "投资", "理财", "宏观经济", "商业财经", "外汇", "债券"),
    ),
    ContentRule(
        path=("搞笑幽默", "搞笑内容", "搞笑段子"),
        keywords=("搞笑", "段子", "沙雕", "整活", "神回复", "鬼畜"),
    ),
    ContentRule(
        path=("宠物生活", "宠物日常", "宠物猫"),
        keywords=("猫咪", "宠物猫", "猫粮", "猫砂", "铲屎官"),
    ),
    ContentRule(
        path=("宠物生活", "宠物日常", "宠物狗"),
        keywords=("狗狗", "宠物狗", "遛狗", "训犬"),
    ),
    ContentRule(
        path=("生活", "分享", "vlog"),
        keywords=("vlog", "生活记录", "日常", "守店日常", "上班日常", "恋爱vlog"),
    ),
    ContentRule(
        path=("时事", "新闻资讯", "民生资讯"),
        keywords=("新闻", "民生", "时讯", "时政", "公益", "军事"),
    ),
)


PROFESSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "工程师": ("工程师",),
    "销售": ("销售",),
    "HR": ("hr", "人力", "招聘"),
    "主播": ("主播",),
    "运营": ("运营",),
    "产品经理": ("产品经理", "pm"),
    "程序员": ("程序员", "码农", "开发"),
    "学生": ("学生",),
    "金融从业者": ("金融从业", "投顾", "基金经理"),
    "创业者": ("创业者", "创业中"),
    "品牌创始人": ("品牌创始人", "主理人"),
    "化妆师": ("化妆师",),
    "服装设计师": ("服装设计师",),
    "厨师": ("厨师", "主厨"),
    "咖啡师": ("咖啡师",),
    "记者": ("记者",),
    "作家": ("作家",),
    "娱评人": ("娱评人",),
    "影评人": ("影评人",),
    "营养师": ("营养师",),
    "医生": ("医生",),
    "摄影师": ("摄影师",),
    "插画师": ("插画师",),
    "室内设计师": ("室内设计师",),
    "画家": ("画家",),
    "平面设计师": ("平面设计师",),
    "主持人": ("主持人",),
    "导演": ("导演",),
    "编剧": ("编剧",),
    "教练": ("教练",),
    "运动员": ("运动员",),
    "舞蹈老师": ("舞蹈老师",),
    "整理师": ("整理师",),
    "育婴师": ("育婴师",),
    "企业高管": ("企业高管",),
    "学者专家": ("专家", "教授", "学者"),
    "职业模特": ("模特",),
    "法律从业者": ("律师", "法律从业", "法务"),
    "航空业从业者": ("航空", "空乘", "机长"),
    "健身/舞蹈教练": ("健身教练", "舞蹈教练"),
    "专业美食从业者": ("餐饮人", "美食从业", "探店达人"),
    "品酒家/调酒师": ("调酒师", "品酒师"),
}


INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "潮流运动": ("潮流运动",),
    "球类": ("篮球", "足球", "羽毛球", "球类"),
    "非球类": ("舞蹈", "游泳", "武术"),
    "室内健身": ("室内健身", "居家健身"),
    "城市运动": ("城市运动", "街头运动"),
    "力量训练": ("力量训练", "撸铁"),
    "跑步健身": ("跑步", "健身"),
    "水上运动": ("冲浪", "潜水", "皮划艇"),
    "登山活动": ("登山", "徒步"),
    "户外露营": ("露营",),
    "手账爱好者": ("手账",),
    "骑行爱好者": ("骑行",),
    "飞盘爱好者": ("飞盘",),
    "数码潮流玩家": ("数码潮流",),
    "绘画": ("绘画",),
    "古玩收藏爱好者": ("古玩", "收藏"),
    "高阶潮玩": ("潮玩", "手办", "盲盒"),
    "美术/画廊/展览": ("展览", "画廊", "美术馆"),
    "歌剧舞台剧": ("舞台剧", "歌剧"),
    "数码爱好者": ("数码", "科技", "电子产品"),
    "二次元人群": ("二次元", "动漫", "cos"),
    "手办爱好者": ("手办",),
    "模型爱好者": ("模型",),
    "街舞爱好者": ("街舞",),
    "书法爱好者": ("书法",),
    "美食爱好者": ("美食爱好者", "吃货"),
    "美食探索": ("美食探索", "探店"),
    "轮滑爱好者": ("轮滑",),
    "国风爱好者": ("国风", "汉服"),
    "收纳": ("收纳",),
    "摄影": ("摄影",),
    "穿搭": ("穿搭",),
    "星座": ("星座",),
    "汽车爱好者": ("汽车爱好者", "车迷"),
    "汉服爱好者": ("汉服",),
    "旅行爱好者": ("旅行爱好者", "旅行"),
    "自驾旅行": ("自驾",),
    "国内旅行": ("国内旅行",),
    "海外旅行": ("海外旅行", "出境游"),
}


LIFE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "备孕中": ("备孕",),
    "孕期中": ("孕期中",),
    "妈妈": ("妈妈", "宝妈"),
    "萌娃": ("萌娃",),
    "爸爸": ("爸爸", "奶爸"),
    "孕妈": ("孕妈",),
    "铲屎官": ("铲屎官",),
    "独居人群": ("独居",),
    "留学背景": ("留学", "留学生"),
    "海外华人": ("海外华人",),
    "外国人": ("外国人", "外籍"),
    "混血儿": ("混血",),
    "考公过来人": ("考公上岸", "考公过来人"),
    "考研过来人": ("考研上岸", "考研过来人"),
    "法考过来人": ("法考过来人",),
    "注会过来人": ("注会过来人",),
}


RELATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "情侣": ("情侣", "恋爱", "男朋友", "女朋友"),
    "夫妻": ("夫妻", "老公", "老婆"),
    "家庭": ("家庭", "一家人"),
    "朋友": ("朋友",),
    "同事": ("同事",),
    "亲子": ("亲子", "带娃"),
    "个人": ("我自己", "独自", "本人"),
    "闺蜜": ("闺蜜",),
    "兄弟": ("兄弟",),
}


MONETIZATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "商单广告": ("广告合作", "商务合作", "品牌合作", "广告投放", "赞助"),
    "直播带货": ("直播带货", "直播专拍", "直播下单", "直播福利"),
    "橱窗带货": ("橱窗", "小黄车", "商品链接", "店铺链接", "下单链接"),
    "私域引流": ("加微信", "加vx", "私信我", "进群", "社群", "私域"),
    "品牌种草": ("种草", "开箱", "测评", "评测", "入手", "同款", "好物", "购买"),
}


PROFILE_TAG_LIBRARY = {
    "profession": set(PROFESSION_TAGS),
    "interest": set(INTEREST_TAGS),
    "life": set(LIFE_TAGS),
    "appearance_relation": set(APPEARANCE_RELATION_TAGS),
}


@lru_cache(maxsize=1)
def content_label_pool() -> set[str]:
    labels: set[str] = set()
    for line in CONTENT_TAXONOMY_LINES:
        for segment in line:
            for token in re.split(r"\s*/\s*|,\s*|、", segment):
                cleaned = token.strip()
                if cleaned:
                    labels.add(cleaned)
    return labels
