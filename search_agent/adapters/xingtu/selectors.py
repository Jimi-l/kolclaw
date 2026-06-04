from urllib.parse import parse_qs, unquote, urlparse


BASE_URL = "https://www.xingtu.cn/"
CREATOR_BACKEND_HOME_URL = "https://www.xingtu.cn/ad/creator/index"
CREATOR_BACKEND_HOME_PATH = "/ad/creator/index"


def is_creator_backend_home_url(url: str) -> bool:
    return urlparse(url).path.rstrip("/") == CREATOR_BACKEND_HOME_PATH


def has_creator_backend_redirect(url: str) -> bool:
    query = parse_qs(urlparse(url).query)
    redirect_values = query.get("redirect_uri", [])
    return any(unquote(value).rstrip("/") == CREATOR_BACKEND_HOME_PATH for value in redirect_values)


SEARCH_BUTTON_SELECTORS = [
    "button:has-text('搜索')",
    "[role='button']:has-text('搜索')",
    "text=搜索",
]

SEARCH_INPUT_SELECTORS = [
    "input[placeholder='输入达人昵称、抖音号或星图ID']",
    "input[placeholder*='输入达人昵称']",
    "input[placeholder*='抖音号']",
    "input[placeholder*='星图ID']",
    "input[placeholder*='达人']",
    "input[placeholder*='搜索']",
    "input[type='text']",
]

RESULT_CARD_SELECTORS = [
    ".author-nickname",
    "[class*='author-nickname']",
    "tbody tr",
    "tr[class*='table']",
    "div[class*='table-row']",
    "div[class*='TableRow']",
    "a[href*='/creator/']",
    "div[class*='creator-card']",
    "div[class*='author-card']",
]

CANDIDATE_NAME_SELECTORS = [
    ".author-nickname",
    "[class*='author-nickname']",
]

CANDIDATE_URL_SELECTORS = [
    "a[href*='/creator/']",
]

CANDIDATE_AVATAR_CLICK_SELECTORS = [
    ".author-info-avatar img",
    "[class*='author-info-avatar'] img",
    ".author-info-avatar",
    "[class*='author-info-avatar']",
    ".author-nickname",
    "[class*='author-nickname']",
    "img",
]

CANDIDATE_FOLLOWER_SELECTORS = [
    "span:has-text('粉丝')",
]

CANDIDATE_TYPE_SELECTORS = [
    "span[class*='type']",
    "div[class*='category']",
]

DETAIL_READY_SELECTORS = [
    "text=达人概览",
    "text=商业能力",
    "text=达人服务报价",
    "text=星图ID",
    "div[class*='author-homepage']",
    "main",
    "div[class*='creator-detail']",
]

RECENT_CURVE_SELECTORS = [
    "text=近15条播放曲线",
    "text=近15条视频播放趋势",
]

LOGIN_HINTS = ["登录", "扫码登录", "请登录后查看"]
QR_LOGIN_HINTS = ["扫码登录", "微信扫码"]
SMS_LOGIN_HINTS = ["手机验证码", "短信验证码"]
CAPTCHA_HINTS = ["验证码", "滑块", "人机验证"]
SESSION_EXPIRED_HINTS = ["会话过期", "请重新登录"]
PERMISSION_DENIED_HINTS = ["暂无权限", "权限不足", "开通权限", "升级后查看"]
ACCESS_RESTRICTED_HINTS = ["访问受限", "账号受限"]
UNREGISTERED_HINTS = ["未入驻星图", "未开通星图", "未找到可用创作者"]
