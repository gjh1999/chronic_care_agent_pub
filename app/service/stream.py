"""工作流流式事件:节点通过 emit_status/emit_token 把进度与文本写入当前请求的队列。

流式接口在后台线程运行工作流,线程内通过 contextvar 挂载事件队列;
节点调用 emit_* 时若队列存在则写入,不存在(普通同步接口/测试)则为空操作。
"""

import contextvars
import queue
import threading
from typing import Any

_stream_sink: contextvars.ContextVar[Any] = contextvars.ContextVar("stream_sink", default=None)


def current_sink():
    return _stream_sink.get()


def emit_status(text: str) -> None:
    sink = _stream_sink.get()
    if sink is not None:
        sink.put(("status", text))


def emit_token(text: str) -> None:
    sink = _stream_sink.get()
    if sink is not None:
        sink.put(("token", text))


def run_workflow_streamed(user_input: str, user_id: str, conversation_id: str, user_confirmed=None) -> queue.Queue:
    """后台线程执行工作流,事件写入返回的队列:("status"|"token", text) 或 ("done", result) / ("error", message)。"""
    q: queue.Queue = queue.Queue()

    def _run() -> None:
        token = _stream_sink.set(q)
        try:
            from app.graph.workflow import run_workflow

            result = run_workflow(
                user_input,
                user_id=user_id,
                conversation_id=conversation_id,
                user_confirmed=user_confirmed,
            )
            q.put(("done", result))
        except Exception as exc:  # noqa: BLE001 - 线程边界必须兜底
            q.put(("error", str(exc)))
        finally:
            _stream_sink.reset(token)

    threading.Thread(target=_run, daemon=True).start()
    return q
