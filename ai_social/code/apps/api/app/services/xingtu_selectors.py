"""Centralized Xingtu selectors.

These are intentionally conservative placeholders. Harden them against the
actual recorder output once the saved codegen script is available in-repo.
"""


class XingtuNavigationSelectors:
    WORKSPACE_SHELL = "main"
    WORKSPACE_READY_TEXT = "巨量星图"
    WORKSPACE_URL = "https://www.xingtu.cn/"
    CONTENT_ROOT = "#layout-content, main"
    WORKSPACE_ACCOUNT_CARD = "[data-testid='workspace-card'], [data-testid='account-card'], [class*='workspace-card'], [class*='account-card'], div"
    WORKSPACE_ACCOUNT_HINT_TEXT = "因赛ID"
    # TODO: Confirm whether the authenticated landing page should be a more specific workspace route.

    CREATOR_SEARCH_ENTRY_TEXT = "找达人"
    CREATOR_SEARCH_ENTRY_FALLBACK = "a:has-text('找达人'), [role='link']:has-text('找达人')"
    # TODO: Replace with a stable sidebar selector if the nav structure becomes clear.


class XingtuFilterSelectors:
    ROOT = "#layout-content, main"
    PANEL = "[data-testid='creator-search-filter-panel'], .filter-container, .search-filter"
    GROUP_TRIGGER = "button"
    DROPDOWN_MENU = "[id^='dropdown-menu-'], [role='menu'], [role='listbox'], .ant-dropdown, .ant-select-dropdown"
    DROPDOWN_OPTION = "[role='menuitem'], [role='option'], li, div"
    MENU_CONFIRM_BUTTON = "button:has-text('确定'), button:has-text('完成')"
    # TODO: Replace with the real filter panel selector and menu structure after selector hardening.

    SECTION_CONTAINER = "[data-testid='filter-section'], .filter-module, .byted-card"
    # TODO: Narrow this to the actual Xingtu filter-section wrapper.

    KEYWORD_INPUT = "input[placeholder*='关键词'], input[placeholder*='达人'], input[placeholder*='搜索']"
    RANGE_INPUTS = "input"
    TAG_OPTION = "button, [role='radio'], [role='checkbox'], label"
    SORT_TRIGGER = "[data-testid='sort-trigger'], .sort-select"
    APPLY_BUTTON = "button:has-text('确定'), button:has-text('应用'), button:has-text('查询')"
    # TODO: Harden around the exact apply button label used on the filter form.


class XingtuResultSelectors:
    CONTENT_ROOT = "#layout-content, main"
    RESULTS_CONTAINER = "[data-testid='creator-search-results'], table, [role='table']"
    ROWS = "tbody tr, [role='rowgroup'] [role='row']"
    CLICKABLE_ITEMS = "[data-testid='creator-card'], [class*='author-card'], [data-testid='creator-name'], .author-nickname, .author-name, a[href*='author'], a[href*='creator']"
    ROW_NAME = "a, [role='link'], .author-nickname, .author-name"
    ROW_COLUMNS = "td, [role='cell']"
    # TODO: Replace cell-level selectors with named column selectors after recorder review.


class XingtuDetailSelectors:
    PAGE_READY = "main"
    PAGE_BODY = "body"
    HEADER_NAME = ".author-info .name, .author-info, [data-testid='creator-name'], [class*='creator-name'], h1, h2"
    HEADER_TAGS = ".tag, [data-testid='creator-tag'], [class*='tag']"
    METRIC_BLOCKS = "[data-testid='metric-block'], .metric-card, .data-card"
    METRIC_LABEL = ".label, .title, .name"
    METRIC_VALUE = ".value, .num, .content"
    SECTION_BLOCKS = "section, .module-card, .byted-card"
    SECTION_TITLE = "h2, h3, .title"
    SECTION_BODY = ".content, .body, .section-body"
    PRICE_BLOCKS = "[data-testid='price-card'], .price-card, .quote-card"
    # TODO: Replace with real detail-page selectors for metric groups, pricing cards, and narrative sections.


OPTIONAL_POPUP_CLOSE_SELECTORS = (
    "button:has-text('知道了')",
    "button:has-text('关闭')",
    "button:has-text('稍后再说')",
    "button:has-text('取消')",
    "button[aria-label='关闭']",
    "button[aria-label='Close']",
    ".ant-modal-close",
    ".el-dialog__headerbtn",
)
# TODO: Keep only popups that are required for deterministic navigation after recorder review.
