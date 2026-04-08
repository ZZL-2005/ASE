#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

EVENT_COLORS = {
    "message.inbound": "inbound",
    "message.outbound": "outbound",
    "llm.call": "llm",
    "tool.call": "tool",
    "default": "other",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert trajectory JSONL logs into a readable standalone HTML file."
    )
    parser.add_argument("input", help="Input JSONL file path")
    parser.add_argument(
        "-o", "--output", help="Output HTML file path. Defaults to input path with .html suffix"
    )
    parser.add_argument(
        "--title", default="Trajectory Viewer", help="Page title shown in the HTML"
    )
    parser.add_argument(
        "--max-preview-chars",
        type=int,
        default=400,
        help="Maximum characters shown in event preview before truncation",
    )
    return parser.parse_args()


def safe_read_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], List[Tuple[int, str]]]:
    events: List[Dict[str, Any]] = []
    bad_lines: List[Tuple[int, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    obj["_line_no"] = idx
                    events.append(obj)
                else:
                    bad_lines.append((idx, "JSON root is not an object"))
            except Exception as exc:
                bad_lines.append((idx, str(exc)))
    return events, bad_lines


def fmt_dt(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def short_text(value: Any, max_chars: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def pretty_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def detect_preview(event: Dict[str, Any], max_chars: int) -> str:
    event_type = event.get("type", "")
    data = event.get("data", {}) or {}

    if event_type.startswith("message."):
        return short_text(data.get("content", ""), max_chars)

    if event_type == "llm.call":
        response = data.get("response")
        prompt = data.get("prompt")
        model = data.get("model")
        usage = ((data.get("metadata") or {}).get("usage") or {})
        prefix = []
        if model:
            prefix.append(f"model={model}")
        if usage:
            pt = usage.get("prompt_tokens")
            ct = usage.get("completion_tokens")
            prefix.append(f"tokens={pt}/{ct}")
        prefix_text = " | ".join(prefix)
        body = short_text(response if response not in (None, "") else prompt, max_chars)
        return f"{prefix_text}\n{body}".strip()

    if event_type == "tool.call":
        tool = data.get("tool", "unknown_tool")
        params = short_text(data.get("params", {}), max_chars // 2)
        result = short_text(data.get("result", ""), max_chars)
        return f"tool={tool}\nparams={params}\nresult={result}".strip()

    return short_text(data if data else event, max_chars)


def build_stats(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(e.get("type", "unknown") for e in events)
    sandbox_counts = Counter(e.get("sandbox", "unknown") for e in events)
    channel_counts = Counter()
    tool_counts = Counter()
    model_counts = Counter()
    chat_counts = Counter()

    for e in events:
        data = e.get("data", {}) or {}
        if isinstance(data, dict):
            if data.get("channel"):
                channel_counts[data["channel"]] += 1
            if data.get("chat_id"):
                chat_counts[str(data["chat_id"])] += 1
            if e.get("type") == "tool.call" and data.get("tool"):
                tool_counts[data["tool"]] += 1
            if e.get("type") == "llm.call" and data.get("model"):
                model_counts[data["model"]] += 1

    timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
    start_ts = fmt_dt(min(timestamps)) if timestamps else "-"
    end_ts = fmt_dt(max(timestamps)) if timestamps else "-"

    return {
        "total": len(events),
        "counts": counts,
        "sandboxes": sandbox_counts,
        "channels": channel_counts,
        "tools": tool_counts,
        "models": model_counts,
        "chat_ids": chat_counts,
        "start": start_ts,
        "end": end_ts,
    }


def render_counter_table(counter: Counter, col_a: str, col_b: str) -> str:
    if not counter:
        return '<div class="muted">无</div>'
    rows = []
    for key, value in counter.most_common():
        rows.append(
            f"<tr><td>{html.escape(str(key))}</td><td class='num'>{value}</td></tr>"
        )
    return (
        "<table class='mini-table'>"
        f"<thead><tr><th>{html.escape(col_a)}</th><th>{html.escape(col_b)}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_event(event: Dict[str, Any], index: int, max_preview_chars: int) -> str:
    event_type = event.get("type", "unknown")
    style_class = EVENT_COLORS.get(event_type, EVENT_COLORS["default"])
    data = event.get("data", {}) or {}

    badge_parts = [event_type]
    if event.get("sandbox"):
        badge_parts.append(str(event["sandbox"]))
    if isinstance(data, dict) and data.get("channel"):
        badge_parts.append(str(data["channel"]))

    header_badges = "".join(
        f"<span class='badge'>{html.escape(part)}</span>" for part in badge_parts
    )
    preview = html.escape(detect_preview(event, max_preview_chars))
    preview = preview.replace("\n", "<br>")

    meta_items = {
        "line": event.get("_line_no"),
        "timestamp": fmt_dt(event.get("timestamp")),
        "chat_id": data.get("chat_id") if isinstance(data, dict) else None,
    }
    meta_html = "".join(
        f"<div><span class='meta-key'>{html.escape(str(k))}</span><span>{html.escape(str(v))}</span></div>"
        for k, v in meta_items.items()
        if v not in (None, "")
    )

    return f"""
    <details class="event {style_class}" open>
      <summary>
        <div class="event-top">
          <div class="event-index">#{index}</div>
          <div class="event-preview">{preview}</div>
        </div>
        <div class="event-badges">{header_badges}</div>
      </summary>
      <div class="event-body">
        <div class="meta-grid">{meta_html}</div>
        <div class="panel">
          <div class="panel-title">完整 JSON</div>
          <pre>{pretty_json(event)}</pre>
        </div>
      </div>
    </details>
    """


def build_html(title: str, input_name: str, events: List[Dict[str, Any]], bad_lines: List[Tuple[int, str]], max_preview_chars: int) -> str:
    stats = build_stats(events)
    event_html = "\n".join(
        render_event(event, idx, max_preview_chars) for idx, event in enumerate(events, start=1)
    )
    bad_line_html = (
        "".join(
            f"<li>第 {line_no} 行：{html.escape(reason)}</li>" for line_no, reason in bad_lines
        )
        if bad_lines
        else "<li>无</li>"
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121933;
      --panel-2: #0f1530;
      --text: #e7ecff;
      --muted: #9aa7d1;
      --border: #26345f;
      --accent: #7aa2ff;
      --inbound: #153a2a;
      --outbound: #3b2e17;
      --llm: #2d1d4a;
      --tool: #19324a;
      --other: #24283b;
      --shadow: 0 10px 30px rgba(0,0,0,.25);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #0a0f1c 100%);
      color: var(--text);
      line-height: 1.55;
    }}
    .page {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(122,162,255,.18), rgba(122,162,255,.05));
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 22px 24px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    .sub {{ color: var(--muted); font-size: 14px; }}
    .layout {{ display: grid; grid-template-columns: 360px 1fr; gap: 20px; align-items: start; }}
    .sidebar, .content {{ min-width: 0; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      box-shadow: var(--shadow);
      margin-bottom: 16px;
    }}
    .card h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .stat {{ background: var(--panel-2); border: 1px solid var(--border); border-radius: 12px; padding: 12px; }}
    .stat .label {{ color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    .stat .value {{ font-size: 22px; font-weight: 700; }}
    .mini-table {{ width: 100%; border-collapse: collapse; font-size: 13px; overflow: hidden; border-radius: 10px; }}
    .mini-table th, .mini-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    .mini-table th {{ color: var(--muted); font-weight: 600; }}
    .mini-table .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .muted {{ color: var(--muted); }}
    .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
    .toolbar input {{
      flex: 1;
      min-width: 220px;
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 14px;
    }}
    .toolbar button {{
      background: #1d2a52;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 14px;
      cursor: pointer;
    }}
    .event {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-left-width: 5px;
      border-radius: 16px;
      margin-bottom: 14px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}
    .event.inbound {{ border-left-color: #38d996; background: linear-gradient(180deg, rgba(56,217,150,.08), rgba(18,25,51,1)); }}
    .event.outbound {{ border-left-color: #f0b35f; background: linear-gradient(180deg, rgba(240,179,95,.08), rgba(18,25,51,1)); }}
    .event.llm {{ border-left-color: #b084ff; background: linear-gradient(180deg, rgba(176,132,255,.08), rgba(18,25,51,1)); }}
    .event.tool {{ border-left-color: #56b6ff; background: linear-gradient(180deg, rgba(86,182,255,.08), rgba(18,25,51,1)); }}
    .event.other {{ border-left-color: #8691b8; }}
    .event summary {{ list-style: none; cursor: pointer; padding: 14px 16px; }}
    .event summary::-webkit-details-marker {{ display: none; }}
    .event-top {{ display: grid; grid-template-columns: 56px 1fr; gap: 12px; align-items: start; }}
    .event-index {{
      font-weight: 700;
      color: var(--accent);
      font-variant-numeric: tabular-nums;
      background: rgba(122,162,255,.12);
      border: 1px solid var(--border);
      border-radius: 10px;
      text-align: center;
      padding: 6px 8px;
    }}
    .event-preview {{ white-space: normal; word-break: break-word; }}
    .event-badges {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      background: rgba(255,255,255,.03);
    }}
    .event-body {{ padding: 0 16px 16px; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin-bottom: 14px; }}
    .meta-grid > div {{ background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; padding: 10px; }}
    .meta-key {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    .panel {{ background: var(--panel-2); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
    .panel-title {{ padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--muted); font-size: 13px; }}
    pre {{ margin: 0; padding: 14px; overflow: auto; font-size: 12px; line-height: 1.5; }}
    ul {{ margin: 8px 0 0 18px; }}
    .footer {{ color: var(--muted); font-size: 12px; margin-top: 20px; }}
    @media (max-width: 1100px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>{html.escape(title)}</h1>
      <div class="sub">输入文件：{html.escape(input_name)}</div>
      <div class="sub">时间范围：{html.escape(stats['start'])} → {html.escape(stats['end'])}</div>
    </div>

    <div class="layout">
      <aside class="sidebar">
        <div class="card">
          <h2>概览</h2>
          <div class="stat-grid">
            <div class="stat"><div class="label">事件总数</div><div class="value">{stats['total']}</div></div>
            <div class="stat"><div class="label">坏行数</div><div class="value">{len(bad_lines)}</div></div>
          </div>
        </div>

        <div class="card">
          <h2>事件类型统计</h2>
          {render_counter_table(stats['counts'], 'type', 'count')}
        </div>

        <div class="card">
          <h2>工具调用统计</h2>
          {render_counter_table(stats['tools'], 'tool', 'count')}
        </div>

        <div class="card">
          <h2>模型统计</h2>
          {render_counter_table(stats['models'], 'model', 'count')}
        </div>

        <div class="card">
          <h2>聊天 ID 统计</h2>
          {render_counter_table(stats['chat_ids'], 'chat_id', 'count')}
        </div>

        <div class="card">
          <h2>解析异常</h2>
          <ul>{bad_line_html}</ul>
        </div>
      </aside>

      <main class="content">
        <div class="toolbar">
          <input id="searchBox" type="text" placeholder="搜索 type / chat_id / 内容 / 模型 / 工具名...">
          <button type="button" onclick="expandAll()">全部展开</button>
          <button type="button" onclick="collapseAll()">全部收起</button>
        </div>
        <div id="events">{event_html}</div>
      </main>
    </div>

    <div class="footer">Generated by trajectory_jsonl_to_html.py</div>
  </div>

  <script>
    const searchBox = document.getElementById('searchBox');
    const eventNodes = Array.from(document.querySelectorAll('.event'));

    function normalize(text) {{
      return (text || '').toLowerCase();
    }}

    function applyFilter() {{
      const q = normalize(searchBox.value.trim());
      for (const node of eventNodes) {{
        const hay = normalize(node.innerText);
        node.style.display = (!q || hay.includes(q)) ? '' : 'none';
      }}
    }}

    function expandAll() {{
      for (const node of eventNodes) node.open = true;
    }}

    function collapseAll() {{
      for (const node of eventNodes) node.open = false;
    }}

    searchBox.addEventListener('input', applyFilter);
    window.expandAll = expandAll;
    window.collapseAll = collapseAll;
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(input_path.suffix + ".html")

    events, bad_lines = safe_read_jsonl(input_path)
    page_title = args.title
    html_text = build_html(page_title, input_path.name, events, bad_lines, args.max_preview_chars)

    output_path.write_text(html_text, encoding="utf-8")
    print(f"Wrote HTML to: {output_path}")
    print(f"Parsed events: {len(events)}")
    print(f"Bad lines: {len(bad_lines)}")


if __name__ == "__main__":
    main()
