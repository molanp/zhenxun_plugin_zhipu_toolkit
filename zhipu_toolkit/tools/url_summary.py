from bs4 import BeautifulSoup

from zhenxun.utils.http_utils import AsyncHttpx

from ._model import Tool


class UrlSummaryTool(Tool):
    """网页内容抓取工具"""

    def __init__(self):
        super().__init__(
            name="url_summary",
            description=(
                "抓取指定URL的网页正文内容，返回纯文本形式的网页主体文本。"
                "需提供有效的公开网页链接"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网页的完整URL地址",
                    },
                },
                "required": ["url"],
            },
            func=self.summary,
        )

    async def summary(self, url: str) -> str:
        res = await AsyncHttpx.get(url)
        res = BeautifulSoup(res.text, "html.parser").get_text()
        return res
