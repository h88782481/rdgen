"""
RDGen 中文 i18n 注入中间件（本地增强，0 侵入模板/表单/视图）。

原理：把 rdgenerator/i18n/overlay.js 作为一段 <script> 注入到每个
text/html 响应中，由浏览器在运行时把英文替换为中文。

只需在此维护词典的地方是 overlay.js；上游同步代码时，本文件与该 JS
均为新增文件，通常不会产生合并冲突。唯一需要改动的上游文件是
settings.py（在其末尾追加一行注册本中间件）。
"""
import os

_OVERLAY_PATH = os.path.join(os.path.dirname(__file__), "i18n", "overlay.js")
_MARKER = "data-rdgen-i18n"

# 缓存注入片段，仅在文件被修改时重新读取（便于开发时改词典无需重启太频繁）。
_cache = {"mtime": None, "html": ""}


def _get_snippet():
    try:
        mtime = os.path.getmtime(_OVERLAY_PATH)
    except OSError:
        return ""
    if _cache["mtime"] != mtime:
        try:
            with open(_OVERLAY_PATH, "r", encoding="utf-8") as f:
                js = f.read()
        except OSError:
            return ""
        _cache["html"] = "\n<script " + _MARKER + ">\n" + js + "\n</script>\n"
        _cache["mtime"] = mtime
    return _cache["html"]


class I18nInjectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self._inject(self.get_response(request))

    def _inject(self, response):
        try:
            if getattr(response, "streaming", False):
                return response
            if getattr(response, "status_code", 200) != 200:
                return response
            ctype = response.get("Content-Type", "") if hasattr(response, "get") else ""
            if "text/html" not in ctype:
                return response

            charset = getattr(response, "charset", None) or "utf-8"
            content = response.content.decode(charset)
            if _MARKER in content:  # 避免重复注入
                return response

            snippet = _get_snippet()
            if not snippet:
                return response

            lower = content.lower()
            pos = lower.rfind("</head>")
            if pos == -1:
                pos = lower.rfind("</body>")
            if pos == -1:
                new_content = content + snippet
            else:
                new_content = content[:pos] + snippet + content[pos:]

            data = new_content.encode(charset)
            response.content = data
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(data))
            return response
        except Exception:
            # 任何异常都不能影响正常页面返回
            return response
