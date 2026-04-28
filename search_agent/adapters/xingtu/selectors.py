BASE_URL = "https://www.xingtu.cn/"

SEARCH_INPUT_SELECTORS = [
    "input[placeholder*='达人']",
    "input[placeholder*='搜索']",
    "input[type='text']",
]

RESULT_CARD_SELECTORS = [
    "a[href*='/creator/']",
    "div[class*='creator-card']",
    "div[class*='author-card']",
]

CANDIDATE_NAME_SELECTORS = [
    "h3",
    "span[class*='name']",
]

CANDIDATE_FOLLOWER_SELECTORS = [
    "span:has-text('粉丝')",
]

CANDIDATE_TYPE_SELECTORS = [
    "span[class*='type']",
    "div[class*='category']",
]

DETAIL_READY_SELECTORS = [
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
