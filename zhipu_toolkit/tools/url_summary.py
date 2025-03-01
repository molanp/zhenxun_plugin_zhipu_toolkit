from bs4 import BeautifulSoup

from zhenxun.utils.http_utils import AsyncHttpx

from ._model import Tool


class UrlSummaryTool(Tool):
    def __init__(self):
        super().__init__(
            name="url_summary",
            description="用于查看链接的内容",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网页url",
                    }
                },
                "required": ["url"],
            },
            func=self.summary,
        )

    async def summary(self, session, url: str) -> str:
        res = await AsyncHttpx.get(url)
        res = BeautifulSoup(res.text, "html.parser").get_text()
        return res
