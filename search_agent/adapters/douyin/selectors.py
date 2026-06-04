BASE_URL = "https://www.douyin.com/"

HOME_READY_SELECTORS = [
    "[data-e2e='feed-active-video']",
    "a[href*='/video/']",
    "div[data-e2e*='feed']",
    "main",
]

ACTIVE_CARD_SELECTORS = [
    "[data-e2e='feed-active-video']",
    "div[data-e2e*='feed-item']",
    "div[class*='recommend'] article",
]

FEED_ENTRY_SELECTORS = [
    "a:has-text('推荐')",
    "[role='link']:has-text('推荐')",
    "a:has-text('精选')",
    "[role='link']:has-text('精选')",
    "text=推荐",
    "text=精选",
]

JINGXUAN_RECOMMEND_SELECTORS = [
    "a:has-text('推荐')",
    "[role='link']:has-text('推荐')",
    "button:has-text('推荐')",
    "[role='button']:has-text('推荐')",
    "text=推荐",
]

BLOCKING_UI_DISMISS_SELECTORS = [
    "button:has-text('取消')",
    "button:has-text('关闭')",
    "button:has-text('稍后再说')",
    "button:has-text('以后再说')",
    "button:has-text('继续网页版')",
    "button:has-text('稍后')",
    "text=取消",
    "text=关闭",
    "text=稍后再说",
    "text=以后再说",
    "[aria-label='关闭']",
]

FEED_ACK_BUTTON_SELECTORS = [
    "button:has-text('我知道了')",
    "[role='button']:has-text('我知道了')",
    "text=我知道了",
]

NEXT_VIDEO_BUTTON_SELECTORS = [
    ".xgplayer-playswitch-next",
    ".xgplayer-playswitch-next > .semi-icon",
    ".xgplayer-playswitch-next > .semi-icon > svg",
    ".xgplayer-playswitch-next > .semi-icon > svg > g > path",
]

RETURN_TO_FEED_SELECTORS = [
    "text=返回推荐",
    "a:has-text('返回推荐')",
    "button:has-text('返回推荐')",
]

VIDEO_LINK_SELECTORS = [
    "a[href*='/video/']",
]

CREATOR_LINK_SELECTORS = [
    "a[href*='/user/']",
    "[data-e2e='video-author-name']",
]

CREATOR_NAME_SELECTORS = [
    ".account-name-text",
    ".account-name.userAccountTextHover",
    ".account",
    "[data-e2e='video-author-name']",
    "a[href*='/user/'] span",
    "h1 span",
]

PUBLISH_TIME_SELECTORS = [
    "[data-e2e='video-publish-time']",
    "span[class*='publish']",
]

LIKE_COUNT_SELECTORS = [
    "[data-e2e='like-count']",
    "button[aria-label*='点赞'] span",
]

COMMENT_COUNT_SELECTORS = [
    "[data-e2e='comment-count']",
    "button[aria-label*='评论'] span",
]

COMMENT_BUTTON_SELECTORS = [
    "[data-e2e='feed-comment-icon']",
    "[data-e2e='comment-icon']",
    "button:has([data-e2e='comment-count'])",
    "[role='button']:has([data-e2e='comment-count'])",
    "button[aria-label*='评论']",
    "[role='button'][aria-label*='评论']",
    "[data-e2e='comment-count']",
    "button:has-text('评论')",
]

COMMENT_PANEL_SELECTORS = [
    "[data-e2e='comment-list']",
    "[data-e2e='feed-comment-list']",
    "[data-e2e*='comment-list']",
    "div[class*='comment'][class*='panel']",
    "div[class*='comment'][class*='list']",
    "div[class*='CommentList']",
    "div[class*='comment-list']",
    "aside:has-text('评论')",
]

COMMENT_ITEM_SELECTORS = [
    "[data-e2e='comment-item']",
    "[data-e2e*='comment-item']",
    "div[class*='commentItem']",
    "div[class*='CommentItem']",
    "div[class*='comment-item']",
    "li[class*='comment']",
]

COMMENT_CLOSE_SELECTORS = [
    "button[aria-label*='关闭']",
    "button:has-text('关闭')",
    "button:has-text('收起')",
    "button:has-text('返回')",
    "[role='button']:has-text('关闭')",
    "[data-e2e='close']",
    "[data-icon='close']",
]

LOGIN_MODAL_TEXT_HINTS = [
    "登录后免费畅享高清视频",
    "登录后免费畅享高清内容",
    "登录后免费畅享高清画质",
    "一键登录",
    "登录其他账号",
]

LOGIN_MODAL_CLOSE_SELECTORS = [
    "div[role='dialog'] [aria-label='关闭']",
    "div[role='dialog'] button[aria-label='关闭']",
    "div[role='dialog'] button:has-text('关闭')",
    "div[role='dialog'] [data-e2e='close']",
    "[aria-label='关闭']",
    "button[aria-label='关闭']",
]

FEED_SIDE_PANEL_HINTS = [
    "TA的作品",
    "相关推荐",
    "问AI",
    "大家都在搜",
    "全部评论",
]

FEED_SIDE_PANEL_CLOSE_SELECTORS = [
    "button[aria-label*='关闭']",
    "[aria-label='关闭']",
    "[data-e2e='close']",
    "[data-icon='close']",
]

FAVORITE_COUNT_SELECTORS = [
    "[data-e2e='collect-count']",
    "button[aria-label*='收藏'] span",
]

SHARE_COUNT_SELECTORS = [
    "[data-e2e='share-count']",
    "button[aria-label*='分享'] span",
]

PROFILE_READY_SELECTORS = [
    "div[data-e2e='user-tab-list']",
    "div[class*='user-main']",
    "a[href*='/video/']",
    "main",
]

PROFILE_NAME_SELECTORS = [
    "h1 span",
    "[data-e2e='user-title']",
]

PROFILE_BIO_SELECTORS = [
    "[data-e2e='user-desc']",
    "div[class*='signature']",
]

PROFILE_PANEL_STATS_SELECTORS = [
    ".author-card-user-stats",
]

FOLLOWER_COUNT_SELECTORS = [
    "[data-e2e='user-following-count'] + span",
    "span:has-text('粉丝')",
]

TOTAL_LIKED_COUNT_SELECTORS = [
    "span:has-text('获赞')",
    "span:has-text('点赞')",
]

PROFILE_WORKS_TAB_SELECTORS = [
    "text=TA的作品",
    "div:has-text('TA的作品')",
    "[role='tab']:has-text('TA的作品')",
    ".semi-tabs-tab:has-text('TA的作品')",
    "button:has-text('TA的作品')",
]

PROFILE_VIDEO_CARD_SELECTORS = [
    "a[href*='/video/']",
    "a[href*='/note/']",
    "li:has(a[href*='/video/'])",
    "li:has(a[href*='/note/'])",
    "div[data-e2e*='user-post-item']",
    "div:has(a[href*='/video/'])",
    "div:has(a[href*='/note/'])",
]

PROFILE_VIDEO_TITLE_SELECTORS = [
    "p",
    "span",
]

PROFILE_VIDEO_LIKE_SELECTORS = [
    "span:has(svg)",
    "[data-e2e='video-like-count']",
]

PAUSE_BUTTON_SELECTORS = [
    "button[aria-label*='暂停']",
    "div[aria-label*='暂停']",
]

PROFILE_TEXT_HINTS = ["粉丝", "获赞", "作品", "喜欢", "IP属地"]
FEED_TEXT_HINTS = ["点赞", "评论", "收藏", "分享", "推荐", "精选", "听抖音"]
GLOBAL_CHROME_HINTS = ["精选", "推荐", "搜索", "关注", "朋友", "我的", "直播", "放映厅", "短剧", "小游戏"]
INLINE_NOISE_HINTS = [
    "登录后分享给朋友",
    "一键登录",
    "登录即同意用户协议和隐私政策",
    "登录其他账号",
    "复制链接",
    "登录后可发布弹幕",
    "发送",
    "倍速",
    "智能",
    "清屏",
    "连播",
    "顺序连播",
    "听抖音",
    "识别画面",
    "正在播放",
]
METADATA_NOISE_HINTS = [
    "TA的作品",
    "相关推荐",
    "问AI",
    "大家都在搜",
    "全部评论",
    "作者回复过",
    "分享",
    "回复",
    "展开",
    "条回复",
]
AUTHOR_STATEMENT_HINTS = [
    "作者声明：",
    "作者声明:",
    "疑似使用了 AI 生成技术，请谨慎甄别",
    "内容来源于网络",
    "虚构演绎，仅供娱乐",
]
LEGAL_FOOTER_HINTS = [
    "京ICP备",
    "京公网安备",
    "广播电视节目制作经营许可证",
    "网络文化许可证",
    "互联网宗教信息服务许可证",
    "药品医疗器械网络信息服务备案",
    "互联网新闻信息服务",
]
EXTERNAL_APP_HINTS = [
    "打开抖音",
    "App内打开",
    "APP内打开",
    "立即打开",
    "打开看看",
    "继续打开",
    "xdg-open",
    "Open xdg-open",
    "外部应用",
]
DOWNLOAD_PAGE_HINTS = [
    "下载抖音",
    "下载抖音客户端",
    "下载APP",
    "前往下载",
    "去下载",
    "安装抖音",
    "打开抖音极速版",
]
FOOTER_ABNORMAL_HINTS = [
    "京ICP备",
    "网络文化经营许可证",
    "中国互联网举报中心",
]

LOGIN_HINTS = ["扫码登录", "手机号登录", "请登录", "登录查看更多内容"]
QR_LOGIN_HINTS = ["扫码登录", "打开抖音扫码登录"]
SMS_LOGIN_HINTS = ["短信登录", "验证码登录", "手机号登录"]
CAPTCHA_HINTS = [
    "验证码",
    "滑块",
    "人机验证",
    "拖动滑块",
    "请完成下列验证后继续",
    "完成下列验证后继续",
    "按住左边按钮拖动完成上方拼图",
    "拖动完成上方拼图",
    "上方拼图",
]
CAPTCHA_MODAL_SELECTORS = [
    "div[role='dialog']:has-text('验证')",
    "div[role='dialog']:has-text('拼图')",
    "div:has-text('请完成下列验证后继续'):has-text('拼图')",
    "div:has-text('按住左边按钮拖动完成上方拼图')",
]
SESSION_EXPIRED_HINTS = ["登录失效", "请重新登录", "会话已过期"]
LIVE_HINTS = ["直播中", "直播间"]
LIVE_ROOM_HINTS = [
    "直播间",
    "本场点赞",
    "说点什么",
    "小时榜",
    "在线观众",
    "连线",
]
LIVE_ROOM_EXIT_SELECTORS = [
    "button:has-text('返回')",
    "button:has-text('退出')",
    "button:has-text('关闭')",
    "text=返回",
    "text=退出",
    "[aria-label='关闭']",
]
LIVE_ROOM_BACK_SELECTORS = [
    "button[aria-label*='返回']",
    "[role='button'][aria-label*='返回']",
    "[data-e2e='back-button']",
    "[data-e2e='live-back-button']",
]
AD_HINTS = ["广告", "推广"]
AI_HINTS = ["内容由AI生成", "AI生成"]
