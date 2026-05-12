import http.cookies
from typing import Any

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot
from nonebot_plugin_uninfo import Uninfo

from zhenxun.services.log import logger
from zhenxun.utils.http_utils import AsyncHttpx


class QQApi:
    """QQ接口"""

    def __init__(self, session: Uninfo):
        self.bot: Bot = get_bot(session.self_id)  # pyright: ignore[reportAttributeAccessIssue]
        self.headers = {
            "Content-type": "application/json;charset=UTF-8",
            "qname-service": "976321:131072",
            "qname-space": "Production",
        }

    async def getCookies(self) -> str:
        """
        获取 QQ 空间相关的Cookies
        """
        try:
            return (await self.bot.get_credentials(domain="qzone.qq.com"))["cookies"]
        except Exception as e:
            logger.error("获取 QQ 登录凭证失败", "zhipu_toolkit.utils.QQApi", e=e)
            raise RuntimeError("获取 QQ 登录凭证失败") from e

    async def getQzone(self, num: int = 20, pos: int = 0) -> dict[str, Any]:
        """
        取说说列表

        :param num: 数量
        :param pos: 偏移量
        :return: QQ 空间数据
        """
        url = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
        ck = await self.getCookies()

        resp = await AsyncHttpx.get(
            url,
            headers={
                "Cookie": ck,
                **self.headers,
            },
            params={
                "uin": self.bot.self_id,
                "ftype": 0,
                "sort": 0,
                "pos": pos,
                "num": num,
                "replynum": 100,
                "g_tk": self.get_gtk(ck),
                "code_version": 1,
                "format": "json",
                "need_private_comment": 1,
            },
        )
        return resp.json()

    async def delQzone(self, tid: str, t1_source: str) -> dict[str, Any]:
        """
        删除说说

        :param tid: tid 参数
        :param t1_source: t1_source 参数
        """
        url = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_delete_v6"
        ck = await self.getCookies()
        resp = await AsyncHttpx.post(
            url,
            headers={
                "Cookie": ck,
                "Content-Type": "application/x-www-form-urlencoded",
                **self.headers,
            },
            params={
                "g_tk": self.get_gtk(ck),
            },
            data={
                "hostuin": self.bot.self_id,
                "tid": tid,
                "t1_source": t1_source,
                "code_version": 1,
                "format": "json",
            },
        )
        return resp.json()

    async def setQzone(self, con: str) -> dict[str, Any]:
        """
        发送说说

        :param con: 内容
        :param img: 图片（如果有）
        """
        url = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
        ck = await self.getCookies()
        data = {
            "syn_tweet_verson": 1,
            "paramstr": 1,
            "con": con,
            "feedversion": 1,
            "ver": 1,
            "ugc_right": 1,
            "to_sign": 1,
            "hostuin": self.bot.self_id,
            "code_version": 1,
            "format": "json",
        }

        resp = await AsyncHttpx.post(
            url,
            headers={
                "Cookie": ck,
                "Content-Type": "application/x-www-form-urlencoded",
                **self.headers,
            },
            params={
                "g_tk": self.get_gtk(ck),
            },
            data=data,
        )
        return resp.json()

    async def getQzoneMsgb(self, num: int = 0, start: int = 0):
        """
        获取留言

        :param num: 数量，为 0 时返回全部
        :param start: 偏移量/开始位置
        """
        url = (
            "https://user.qzone.qq.com/proxy/domain/m.qzone.qq.com/cgi-bin/new/get_msgb"
        )
        ck = await self.getCookies()
        resp = await AsyncHttpx.get(
            url,
            params={
                "uin": self.bot.self_id,
                "hostUin": self.bot.self_id,
                "start": start,
                "s": 0.45779069937151884,
                "format": "json",
                "num": num,
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "g_tk": self.get_gtk(ck),
            },
            headers={
                "Cookie": ck,
                **self.headers,
            },
        )
        return resp.json()

    async def delQzoneMsgb(self, id_: str, uin_id: str):
        """
        删除留言

        :param id_: 留言 id
        :param uin_id: uinId
        """
        url = "https://h5.qzone.qq.com/proxy/domain/m.qzone.qq.com/cgi-bin/new/del_msgb"
        ck = await self.getCookies()
        resp = await AsyncHttpx.post(
            url,
            headers={
                "Cookie": ck,
                "Content-Type": "application/x-www-form-urlencoded",
                **self.headers,
            },
            params={
                "g_tk": self.get_gtk(ck),
            },
            data={
                "hostUin": self.bot.self_id,
                "idList": id_,
                "uinList": uin_id,
                "format": "json",
                "iNotice": 1,
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "ref": "qzone",
                "g_tk": self.get_gtk(ck),
                "json": 1,
            },
        )
        return resp.json()

    def get_gtk(self, ck: str) -> int:
        cookies = http.cookies.SimpleCookie()
        cookies.load(ck)

        skey = cookies.get("skey")
        if skey is None or not skey.value:
            raise ValueError("Cookie 中缺少 'skey' 字段，无法计算 g_tk")

        e = skey
        n = 5381
        for ch in e:
            n += (n << 5) + ord(ch)
        return 2147483647 & n
