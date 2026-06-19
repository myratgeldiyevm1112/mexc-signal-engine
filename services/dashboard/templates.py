"""
services/dashboard/templates.py
HTML templates for the dashboard.
"""
from datetime import datetime, timezone
import json


def _fmt_price(v: float) -> str:
    if v == 0: return "0"
    if v < 0.0001: return f"{v:.8f}".rstrip("0")
    if v < 1: return f"{v:.6f}".rstrip("0")
    if v < 100: return f"{v:.4f}"
    return f"{v:.2f}"


def _status_badge(status: str) -> str:
    colors = {"healthy": "#00e676", "unhealthy": "#ffd740", "down": "#ff1744"}
    color = colors.get(status, "#888")
    return f'<span style="color:{color};font-weight:bold">● {status}</span>'


def render_page(
    signals: list[dict],
    stats: dict,
    by_hour: list[dict],
    top_symbols: list[dict],
    service_statuses: dict,
    redis_stats: dict,
    filters: dict,
    page: int,
) -> str:

    # Build hour chart data
    hours = [0] * 24
    for row in by_hour:
        h = int(row["hour"])
        hours[h] = int(row["count"])
    hours_json = json.dumps(hours)

    # Build top symbols chart data
    sym_labels = json.dumps([r["symbol"].replace("_USDT", "") for r in top_symbols])
    sym_counts = json.dumps([int(r["count"]) for r in top_symbols])

    # Signals table rows
    rows_html = ""
    for s in signals:
        dt = s["created_at"]
        if hasattr(dt, "strftime"):
            time_str = dt.strftime("%m-%d %H:%M")
        else:
            time_str = str(dt)[:16]

        direction = s["direction"]
        dir_color = "#00e676" if direction == "LONG" else "#ff1744"
        dir_emoji = "🚀" if direction == "LONG" else "🔻"
        sent = "✅" if s["telegram_sent"] else "⏳"
        change = float(s["change_15m"])
        change_color = "#00e676" if change > 0 else "#ff1744"

        rows_html += f"""
        <tr>
            <td>{s['id']}</td>
            <td><b>{s['symbol']}</b></td>
            <td style="color:{dir_color}">{dir_emoji} {direction}</td>
            <td><code>{_fmt_price(float(s['price']))}</code></td>
            <td style="color:{change_color}">{change:+.2f}%</td>
            <td>{float(s['rsi_1h']):.1f}</td>
            <td>{float(s['rsi_15m']):.1f}</td>
            <td>{sent}</td>
            <td>{time_str}</td>
        </tr>"""

    # Service status
    svc_html = ""
    for name, status in service_statuses.items():
        svc_html += f"<div class='svc-item'><b>{name}</b>: {_status_badge(status)}</div>"

    # Filters
    dir_filter = filters.get("direction") or ""
    sym_filter = filters.get("symbol") or ""
    days_val = filters.get("days", 7)

    total = int(stats.get("total") or 0)
    long_c = int(stats.get("long_count") or 0)
    short_c = int(stats.get("short_count") or 0)
    sent_c = int(stats.get("sent_count") or 0)
    avg_change = float(stats.get("avg_change") or 0)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MEXC Signal Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #0d0d14; color: #d0d0e0; font-family: monospace; padding: 20px; }}
        h1 {{ color: #ffd740; margin-bottom: 20px; font-size: 1.4em; }}
        h2 {{ color: #aaa; font-size: 1em; margin-bottom: 10px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }}
        .card {{ background: #1a1a2e; border-radius: 8px; padding: 16px; border: 1px solid #2a2a4e; }}
        .card .val {{ font-size: 1.8em; font-weight: bold; color: #ffd740; }}
        .card .lbl {{ font-size: 0.75em; color: #888; margin-top: 4px; }}
        .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
        .chart-box {{ background: #1a1a2e; border-radius: 8px; padding: 16px; border: 1px solid #2a2a4e; }}
        .services {{ background: #1a1a2e; border-radius: 8px; padding: 16px; border: 1px solid #2a2a4e; margin-bottom: 20px; }}
        .svc-item {{ display: inline-block; margin-right: 20px; margin-top: 6px; font-size: 0.85em; }}
        .redis-info {{ font-size: 0.8em; color: #888; margin-top: 8px; }}
        .filters {{ background: #1a1a2e; border-radius: 8px; padding: 12px; margin-bottom: 16px; border: 1px solid #2a2a4e; }}
        .filters form {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .filters input, .filters select {{ background: #0d0d14; color: #d0d0e0; border: 1px solid #2a2a4e; border-radius: 4px; padding: 6px 10px; font-family: monospace; }}
        .filters button {{ background: #ffd740; color: #0d0d14; border: none; border-radius: 4px; padding: 6px 14px; cursor: pointer; font-weight: bold; }}
        .filters a {{ color: #888; font-size: 0.85em; text-decoration: none; }}
        table {{ width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 8px; overflow: hidden; border: 1px solid #2a2a4e; }}
        th {{ background: #2a2a4e; color: #aaa; padding: 10px 12px; text-align: left; font-size: 0.8em; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #1a1a2e; font-size: 0.82em; }}
        tr:hover {{ background: #1f1f35; }}
        .pagination {{ margin-top: 12px; display: flex; gap: 8px; }}
        .pagination a {{ color: #ffd740; text-decoration: none; padding: 4px 10px; border: 1px solid #ffd740; border-radius: 4px; font-size: 0.85em; }}
        .footer {{ margin-top: 20px; color: #444; font-size: 0.75em; text-align: right; }}
        @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <h1>📊 MEXC Signal Engine — Dashboard</h1>

    <!-- Stats cards -->
    <div class="grid">
        <div class="card"><div class="val">{total}</div><div class="lbl">Всего сигналов ({days_val}д)</div></div>
        <div class="card"><div class="val" style="color:#00e676">{long_c}</div><div class="lbl">LONG сигналов</div></div>
        <div class="card"><div class="val" style="color:#ff1744">{short_c}</div><div class="lbl">SHORT сигналов</div></div>
        <div class="card"><div class="val">{sent_c}</div><div class="lbl">Отправлено в TG</div></div>
        <div class="card"><div class="val">{avg_change:.1f}%</div><div class="lbl">Среднее изменение</div></div>
        <div class="card"><div class="val">{redis_stats.get('ready_symbols', '?')}</div><div class="lbl">Символов в Redis</div></div>
    </div>

    <!-- Services -->
    <div class="services">
        <h2>🔧 Статус сервисов</h2>
        {svc_html}
        <div class="redis-info">
            Redis: BTC_USDT candles →
            5m: {redis_stats.get('btc_5m', '?')} |
            15m: {redis_stats.get('btc_15m', '?')} |
            1h: {redis_stats.get('btc_1h', '?')} |
            DB size: {redis_stats.get('db_size', '?')} keys
        </div>
    </div>

    <!-- Charts -->
    <div class="charts">
        <div class="chart-box">
            <h2>⏰ Сигналы по часам (UTC)</h2>
            <canvas id="hourChart" height="120"></canvas>
        </div>
        <div class="chart-box">
            <h2>🏆 Топ символов</h2>
            <canvas id="symChart" height="120"></canvas>
        </div>
    </div>

    <!-- Filters -->
    <div class="filters">
        <form method="get">
            <select name="direction">
                <option value="">Все направления</option>
                <option value="LONG" {"selected" if dir_filter=="LONG" else ""}>LONG</option>
                <option value="SHORT" {"selected" if dir_filter=="SHORT" else ""}>SHORT</option>
            </select>
            <input type="text" name="symbol" placeholder="Символ (напр. BTC)" value="{sym_filter}">
            <select name="days">
                <option value="1" {"selected" if days_val==1 else ""}>1 день</option>
                <option value="7" {"selected" if days_val==7 else ""}>7 дней</option>
                <option value="30" {"selected" if days_val==30 else ""}>30 дней</option>
                <option value="90" {"selected" if days_val==90 else ""}>90 дней</option>
            </select>
            <button type="submit">🔍 Фильтр</button>
            <a href="/">Сбросить</a>
        </form>
    </div>

    <!-- Signals table -->
    <table>
        <thead>
            <tr>
                <th>#</th><th>Символ</th><th>Направление</th><th>Цена</th>
                <th>Change 15m</th><th>RSI 1h</th><th>RSI 15m</th><th>TG</th><th>Время</th>
            </tr>
        </thead>
        <tbody>
            {rows_html if rows_html else '<tr><td colspan="9" style="text-align:center;color:#888;padding:20px">Сигналов нет</td></tr>'}
        </tbody>
    </table>

    <!-- Pagination -->
    <div class="pagination">
        {"" if page <= 1 else f'<a href="?page={page-1}&days={days_val}&direction={dir_filter}&symbol={sym_filter}">← Назад</a>'}
        <span style="color:#888;font-size:0.85em;padding:4px 8px">Страница {page}</span>
        {"" if len(signals) < 50 else f'<a href="?page={page+1}&days={days_val}&direction={dir_filter}&symbol={sym_filter}">Вперёд →</a>'}
    </div>

    <div class="footer">Обновлено: {now_utc}</div>

    <script>
    const hourData = {hours_json};
    const symLabels = {sym_labels};
    const symCounts = {sym_counts};

    const chartDefaults = {{
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            x: {{ ticks: {{ color: '#888', font: {{ size: 10 }} }}, grid: {{ color: '#1a1a2e' }} }},
            y: {{ ticks: {{ color: '#888', font: {{ size: 10 }} }}, grid: {{ color: '#2a2a4e' }} }}
        }}
    }};

    new Chart(document.getElementById('hourChart'), {{
        type: 'bar',
        data: {{
            labels: Array.from({{length: 24}}, (_, i) => i + 'h'),
            datasets: [{{ data: hourData, backgroundColor: '#ffd740aa', borderColor: '#ffd740', borderWidth: 1 }}]
        }},
        options: chartDefaults
    }});

    new Chart(document.getElementById('symChart'), {{
        type: 'bar',
        data: {{
            labels: symLabels,
            datasets: [{{ data: symCounts, backgroundColor: '#2979ffaa', borderColor: '#2979ff', borderWidth: 1 }}]
        }},
        options: {{ ...chartDefaults, indexAxis: 'y' }}
    }});
    </script>
</body>
</html>"""