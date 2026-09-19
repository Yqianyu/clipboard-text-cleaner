# -*- coding: utf-8 -*-
"""
剪贴板文本清理守护进程

在后台运行，自动监听剪贴板：
    你复制任何文字 -> 脚本自动删除空格/换行/段落标记 -> 写回剪贴板 -> 直接 Ctrl+V 粘贴即可

用法：
    python 清理守护.py                 # 默认规则：删空格 + 换行 + 段落标记
    python 清理守护.py --space         # 保留空格
    python 清理守护.py --keep-newline  # 保留换行
    python 清理守护.py --keep-para     # 保留段落标记
    python 清理守护.py --collapse      # 不删换行，只把连续空行合并为一个

停止：在脚本窗口按 Ctrl+C，或直接关掉窗口。
"""

import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# 64 位 Windows 下必须显式声明句柄类型，否则会被截断成 32 位导致失败
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

# ============ 清理规则（和网页版一致） ============
PARA_MARKS = "¶·■▶●◆▲►‣▪"


def clean(text: str, space=True, newline=True, para=True, tab=True, trim=True, collapse=False) -> str:
    if para:
        for ch in PARA_MARKS:
            text = text.replace(ch, "")
    if tab:
        text = text.replace("\t", "")
    if collapse:
        import re
        text = re.sub(r"[ \t]+\r?\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    elif newline:
        text = text.replace("\r\n", "").replace("\r", "").replace("\n", "")
    if space:
        for ch in (" ", "\u00a0", "\u3000", "\u2002", "\u2003", "\u202f", "\u205f"):
            text = text.replace(ch, "")
    if trim:
        text = text.strip()
    return text


# ============ 剪贴板读写（ctypes 调 Windows API） ============
def get_clipboard():
    """读取剪贴板文字，非文字内容返回 None"""
    if not user32.OpenClipboard(None):
        return None
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.c_wchar_p(p).value or ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard(text: str) -> bool:
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        size = (len(text) + 1) * ctypes.sizeof(ctypes.c_wchar)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, ctypes.c_size_t(size))
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        if not p:
            return False
        try:
            ctypes.memmove(p, ctypes.create_unicode_buffer(text), size)
        finally:
            kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


def main():
    args = sys.argv[1:]
    space = "--space" not in args
    newline = "--keep-newline" not in args
    para = "--keep-para" not in args
    collapse = "--collapse" in args
    quiet = "--quiet" in args

    print("=" * 46)
    print("  剪贴板清理守护已启动")
    print("  规则: " + ", ".join([
        "保留空格" if not space else "删空格",
        "合并空行" if collapse else ("保留换行" if not newline else "删换行"),
        "保留段落标记" if not para else "删段落标记",
    ]))
    print("  复制文字后直接 Ctrl+V 即为清理结果")
    print("  停止: 按 Ctrl+C 或关闭本窗口")
    print("=" * 46)

    last_seen = None  # 上次处理过的内容，防止自己写回后又触发一遍
    while True:
        try:
            text = get_clipboard()
            if text is not None and text != last_seen:
                cleaned = clean(text, space=space, newline=newline,
                                para=para, collapse=collapse)
                if cleaned != text:
                    if set_clipboard(cleaned):
                        last_seen = cleaned
                        if not quiet:
                            print(f"[{time.strftime('%H:%M:%S')}] "
                                  f"已清理 {len(text)} -> {len(cleaned)} 字符")
                else:
                    last_seen = text
            time.sleep(0.4)
        except KeyboardInterrupt:
            print("\n守护已停止。")
            break
        except Exception as e:
            # 剪贴板偶尔被其他程序占用，忽略本次继续
            if not quiet:
                print(f"跳过一次（{e.__class__.__name__}）")
            time.sleep(1)


if __name__ == "__main__":
    main()
