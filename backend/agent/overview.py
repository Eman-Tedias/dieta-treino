"""Fixed 'at a glance' dashboard: training volume + diet kcal per day.

Unlike generate_dashboard, this never touches an LLM. It's a hand-written
HTML template (reusing the same design system as template.py) filled with a
fixed SQL query, so it's free and always reflects the latest data.
"""
import json
import sqlite3

from template import COMPONENTES, TOKENS_CSS
from utils import DB_PATH

_CSS = TOKENS_CSS + COMPONENTES["page_header"]["css"] + COMPONENTES["line_chart"]["css"]

_QUERY = "SELECT data, total_kcal, volume_total FROM v_dieta_treino ORDER BY data"


def _fetch_rows() -> list[dict]:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = con.execute(_QUERY).fetchall()
    finally:
        con.close()
    return [{"data": r[0], "kcal": r[1], "volume": r[2] or 0} for r in rows]


def render_overview_html() -> str:
    rows = _fetch_rows()
    dates = json.dumps([r["data"] for r in rows])
    kcal = json.dumps([r["kcal"] for r in rows])
    volume = json.dumps([r["volume"] for r in rows])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Visão geral</title>
  <style>
{_CSS}
  </style>
</head>
<body>
  <header class="page-header">
    <h1>Visão geral</h1>
    <p>Volume de treino e calorias de dieta por dia.</p>
  </header>

  <div class="card">
    <div class="chart" style="width:100%;height:420px;"></div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script>
    const chart = echarts.init(document.querySelector('.chart'));
    const dates = {dates};
    const kcal = {kcal};
    const volume = {volume};

    chart.setOption({{
      backgroundColor: 'transparent',
      tooltip: {{ trigger: 'axis' }},
      legend: {{ textStyle: {{ color: '#8b91a5' }} }},
      grid: {{ left: 60, right: 60, top: 40, bottom: 60, containLabel: true }},
      xAxis: {{
        type: 'category',
        data: dates,
        axisLabel: {{ color: '#8b91a5' }},
        axisLine: {{ lineStyle: {{ color: '#8b91a5' }} }}
      }},
      yAxis: [
        {{
          type: 'value', name: 'Volume',
          axisLabel: {{ color: '#8b91a5' }},
          splitLine: {{ lineStyle: {{ color: '#1f2330' }} }}
        }},
        {{
          type: 'value', name: 'Kcal',
          axisLabel: {{ color: '#8b91a5' }},
          splitLine: {{ show: false }}
        }}
      ],
      series: [
        {{
          name: 'Volume de treino', type: 'bar', data: volume,
          itemStyle: {{ color: '#4f8cff' }}
        }},
        {{
          name: 'Calorias', type: 'line', yAxisIndex: 1, data: kcal,
          itemStyle: {{ color: '#f4b942' }}, smooth: true
        }}
      ]
    }});

    window.addEventListener('resize', () => chart.resize());
  </script>
</body>
</html>"""
