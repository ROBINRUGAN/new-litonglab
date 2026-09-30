# designed by mew
"""Shared field catalogue for the visual editor, validation, and backups."""


def f(name, label, typ="text", **options):
    return {"name": name, "label": label, "type": typ, **options}


def bi(name, label, typ="text", **options):
    return [
        f(name + "_zh", label + "（中文）", typ, **options),
        f(name + "_en", label + "（英文）", typ, **options),
    ]


def choice(name, label, values, **kw):
    return f(name, label, "choice", choices=[(v, v) for v in values], **kw)


SCHEMAS = {
    "publication": [
        f("title", "论文 / 专利题目", required=True),
        f("authors", "作者", "textarea", required=True),
        f("year", "年份", "year", required=True),
        choice(
            "category",
            "类别",
            [
                "Conference Papers",
                "Journal Papers",
                "Chinese Papers",
                "Preprints",
                "Granted Patents",
            ],
        ),
        f("venue_key", "选择会议 / 期刊目录", "reference", target="venue"),
        f("venueShort", "简称（自定义或覆盖目录）"),
        f("venueFull", "完整名称（自定义或覆盖目录）"),
        choice(
            "track",
            "发表类型",
            ["", "Poster", "Demo", "Workshop", "Short Paper", "Work-in-Progress (WIP)", "Preprint"],
        ),
        choice("ccfRating", "CCF 评级", ["", "A", "B", "C", "unranked"]),
        f("ccfEdition", "评级目录版本（留空继承会刊）"),
        f("ccfSource", "评级依据链接（留空继承会刊）", "url"),
        f("ratingNote", "评级说明", "textarea"),
        f("doi", "DOI", help="只填标识符，如 10.1145/3786677。"),
        f(
            "publishedDate",
            "正式发表日期",
            help="允许 YYYY、YYYY-MM 或 YYYY-MM-DD；不要把录用日期当作发表日期。",
        ),
        f("conferenceYear", "会议届别年份（若与出版年不同）", "year"),
        f("volume", "卷号"),
        f("issue", "期号"),
        f("pages", "页码 / 文章编号"),
        f("citation", "完整引用", "textarea"),
        *bi("abstract", "论文摘要", "textarea"),
        f("links", "论文、代码、演示等链接", "links"),
        f("image", "论文图 / 海报主图", "asset"),
        *bi("imageCaption", "图片说明", "textarea"),
    ],
    "person": [
        *bi("name", "姓名", required=False),
        f("group", "所属分组", "reference", target="group", required=True),
        *bi("role", "身份"),
        *bi("bio", "简介", "rich"),
        f("image", "个人照片", "asset", required=True),
        f("links", "个人主页、邮箱等", "links"),
        f("placeholder", "当前为示例照片", "boolean"),
    ],
    "group": [*bi("title", "分组名称"), choice("layout", "显示方式", ["cards", "faculty"])],
    "photo": [
        *bi("title", "照片标题"),
        f("image", "照片", "asset", required=True),
        f("show_home", "加入首页轮播", "boolean", default=True),
        f("show_people", "显示在成员页", "boolean", default=True),
    ],
    "project": [
        f(
            "slug",
            "页面短名",
            "slug",
            required=True,
            help="用于网址，如 new-project-2027；发布后改名会保留旧网址跳转。",
        ),
        *bi("name", "项目名称"),
        *bi("category", "所属领域"),
        *bi("summary", "项目简介", "textarea"),
        *bi("body", "完整介绍", "rich"),
        f("publications", "相关论文（自动沿用论文库内容）", "references", target="publication"),
        f("image", "项目封面 / 系统图", "asset", required=True),
        f("links", "代码、论文、演示等链接", "links"),
        *bi("seoDescription", "搜索引擎摘要", "textarea"),
    ],
    "news": [
        *bi("title", "新闻正文", "textarea"),
        f("date", "新闻日期", "date", required=True),
        choice("category", "新闻类别", ["Publication", "Award", "Lab update"]),
        f("image", "配图（可选）", "asset"),
        f("links", "相关链接", "links"),
    ],
    "direction": [
        *bi("title", "研究方向"),
        *bi("description", "方向简介", "textarea"),
        f("image", "方向插图", "asset", required=True),
        f("projects", "相关项目", "references", target="project"),
        f("publications", "相关论文", "references", target="publication"),
    ],
    "venue": [
        f("title", "会刊简称", required=True),
        f("full", "完整名称", required=True),
        choice("rating", "CCF 评级", ["A", "B", "C", "unranked"]),
        f("edition", "目录版本", default="2026 · 第七版"),
        f("note", "目录说明", "textarea"),
        f(
            "source",
            "评级来源",
            "url",
            default="https://www.ccf.org.cn/Academic_Evaluation/By_category/",
        ),
    ],
    "page": [
        f("slug", "页面短名", "slug", required=True),
        *bi("title", "页面标题"),
        *bi("description", "页面简介", "textarea"),
        f("image", "页首图片", "asset"),
        *bi("body", "页面正文 / 补充内容", "rich"),
        *bi("seoDescription", "搜索引擎摘要", "textarea"),
    ],
    "navigation": [
        *bi("title", "导航名称"),
        f("url", "链接地址", "url", required=True),
        f("header", "显示在顶部导航", "boolean", default=True),
        f("footer", "显示在页脚", "boolean", default=True),
        f("highlight", "作为顶部强调按钮", "boolean"),
    ],
    "section": [
        choice(
            "component",
            "栏目类型",
            ["hero", "research", "projects", "publications", "people", "news", "join", "content"],
        ),
        *bi("title", "自定义栏目标题（可选）"),
        *bi("body", "自定义图文内容", "rich"),
        f("image", "自定义配图", "asset"),
    ],
    "site": [
        *bi("name", "站点名称"),
        f("logo", "Logo", "asset", required=True),
        f("favicon", "浏览器图标", "asset"),
        f("email", "联系邮箱", "email"),
        *bi("address", "联系地址", "textarea"),
        *bi("footer", "页脚介绍", "rich"),
        f("university_url", "学校网站", "url"),
        *bi("university", "学校名称"),
        choice("default_language", "默认语言", ["en", "zh"]),
        choice("default_theme", "默认主题", ["light", "dark"]),
        f("enable_theme", "显示主题切换", "boolean", default=True),
        *bi("seoDescription", "默认搜索摘要", "textarea"),
    ],
    "home": [
        *bi("title", "Hero 标题", "textarea"),
        *bi("description", "Hero 简介", "textarea"),
        *bi("eyebrow", "Hero 顶部短文字"),
        f("video", "Hero 视频", "asset"),
        f("poster", "Hero 封面", "asset", required=True),
        f("overlay", "视频遮罩深度 (%)", "integer", default=85, min_value=30, max_value=100),
        f("featured_projects", "沉浸展示项目", "references", target="project"),
        f("featured_publications", "代表性论文", "references", target="publication"),
        f("news_limit", "首页新闻数量", "integer", default=4, min_value=1, max_value=30),
        f(
            "carousel_seconds",
            "照片轮播间隔（秒）",
            "integer",
            default=6,
            min_value=3,
            max_value=30,
        ),
        f("join_image", "加入我们横幅照片", "asset"),
        *bi("join_title", "加入我们横幅标题"),
        *bi("join_description", "加入我们横幅说明", "textarea"),
    ],
    "text": [
        f(
            "source",
            "原始界面文案键",
            required=True,
            help="现有文案的定位键，通常保持不变。英文与中文显示值在下面修改。",
        ),
        f("value_zh", "中文显示文字", "textarea"),
        f("value_en", "英文显示文字", "textarea"),
    ],
}


def payload_differs(kind, before, after):
    """Compare editable content while treating absent and empty optional fields alike."""
    for field in SCHEMAS[kind]:
        name = field["name"]
        left, right = before.get(name), after.get(name)
        if left == right:
            continue
        if left in (None, "", [], False) and right in (None, "", [], False):
            continue
        return True
    return False
