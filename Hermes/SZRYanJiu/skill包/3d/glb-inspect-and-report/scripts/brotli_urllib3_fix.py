"""brotlicffi + urllib3 v2 兼容补丁
在任何会触发 HTTPS 请求的脚本顶部 `import brotli_urllib3_fix` 即可。
根因: brotlicffi.Decompressor.decompress() 在 can_accept_more_data()=False 时会抛错,
而 urllib3 v2 假设可以持续喂数据直到 flush()。这里包装 decompress 在该状态时返回 b''。
根治: pip uninstall -y brotlicffi && pip install brotli  (CPython 用官方 brotli)
"""
try:
    import brotlicffi as _brotli
except ImportError:
    try:
        import brotli as _brotli
    except ImportError:
        _brotli = None

if _brotli is not None:
    _orig = _brotli.Decompressor.decompress
    def _safe_decompress(self, data):
        if not self.can_accept_more_data():
            return b''
        return _orig(self, data)
    _brotli.Decompressor.decompress = _safe_decompress
