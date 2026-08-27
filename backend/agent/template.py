"""Design system do dashboard: shell CSS + paleta de componentes + prompts.

Este módulo é a única fonte de verdade visual dos artifacts. O agente
gera HTML seguindo o SHELL_PROMPT e usando apenas os COMPONENTES da paleta.
"""

# ---------------------------------------------------------------------------
# 1. Tokens do design system (CSS variables)
# ---------------------------------------------------------------------------

TOKENS_CSS = """
:root {
  --bg: #0f1117;          /* fundo da página */
  --card: #1a1d27;        /* fundo dos cards */
  --card-border: #262b3a; /* borda sutil dos cards */
  --accent: #4f8cff;      /* azul principal (gráficos, destaques) */
  --accent-2: #22c58b;    /* verde (positivo, segunda série) */
  --accent-3: #f4b942;    /* âmbar (atenção, terceira série) */
  --danger: #e5484d;      /* vermelho (queda, alerta) */
  --text: #e8eaf0;        /* texto principal */
  --text-muted: #8b91a5;  /* texto secundário/eixos */
  --font: 'Inter', 'Segoe UI', system-ui, sans-serif;
  --radius: 12px;
  --gap: 16px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg); color: var(--text);
  font-family: var(--font); padding: 24px;
}
.grid { display: grid; gap: var(--grid-gap, var(--gap)); }
"""

# ---------------------------------------------------------------------------
# 2. Paleta de componentes
#    nome -> {descricao (vai no prompt), css (injetado no artifact)}
# ---------------------------------------------------------------------------

COMPONENTES = {
    "page_header": {
        "descricao": (
            "Cabeçalho do dashboard: <header class='page-header'> com <h1> "
            "(título) e <p> (subtítulo/contexto em texto muted). Um por página."
        ),
        "css": (
            ".page-header{margin-bottom:20px}"
            ".page-header h1{font-size:22px;font-weight:600}"
            ".page-header p{color:var(--text-muted);font-size:14px;margin-top:4px}"
        ),
    },
    "metric_card": {
        "descricao": (
            "Card de número grande: <div class='card metric'> com label pequeno "
            "(<span class='metric-label'>), valor (<strong class='metric-value'>) "
            "e delta opcional (<span class='delta up'>+8%</span> ou "
            "<span class='delta down'>-3%</span>). Use em grid de 2-4 cards."
        ),
        "css": (
            ".card{background:var(--card);border:1px solid var(--card-border);"
            "border-radius:var(--radius);padding:16px}"
            ".metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:var(--gap)}"
            ".metric-label{color:var(--text-muted);font-size:12px;"
            "text-transform:uppercase;letter-spacing:.05em;display:block}"
            ".metric-value{font-size:28px;font-weight:700;display:block;margin-top:6px}"
            ".delta.up{color:var(--accent-2)} .delta.down{color:var(--danger)}"
        ),
    },
    "line_chart": {
        "descricao": (
            "Gráfico de linha para séries temporais (evolução de volume, kcal, "
            "proteína). <div class='card'><div class='chart'></div></div> com "
            "ECharts init no div .chart. Altura mínima 300px."
        ),
        "css": (
            ".chart{width:100%;height:340px}"
            ".card h3{font-size:15px;font-weight:600;margin-bottom:10px}"
        ),
    },
    "bar_chart": {
        "descricao": (
            "Gráfico de barras para comparação entre categorias (volume por "
            "grupo muscular, kcal por dia). Mesma estrutura do line_chart."
        ),
        "css": "",  # herda .chart/.card
    },
    "stacked_bar": {
        "descricao": (
            "Barras empilhadas para composição (macros por dia, volume empilhado "
            "por grupo). ECharts series com stack:'total'. Mesma estrutura."
        ),
        "css": "",
    },
    "data_table": {
        "descricao": (
            "Tabela crua ordenável: <div class='card'><table class='data-table'> "
            "com <thead> estilizado. Máx ~30 linhas visíveis."
        ),
        "css": (
            ".data-table{width:100%;border-collapse:collapse;font-size:13px}"
            ".data-table th{color:var(--text-muted);text-align:left;padding:8px;"
            "border-bottom:1px solid var(--card-border);font-weight:500}"
            ".data-table td{padding:8px;border-bottom:1px solid #1f2330}"
        ),
    },
    "insight_callout": {
        "descricao": (
            "Bloco de análise textual: <div class='callout'> com 1-3 frases de "
            "insight sobre os dados. No máx 3 por página, ao final."
        ),
        "css": (
            ".callout{background:rgba(79,140,255,.08);border-left:3px solid "
            "var(--accent);border-radius:6px;padding:12px 14px;font-size:14px;"
            "margin-top:var(--gap)}"
        ),
    },
}

# ---------------------------------------------------------------------------
# 3. Prompts
# ---------------------------------------------------------------------------

def _paleta_no_prompt(nomes: list[str]) -> str:
    """Formata a descrição dos componentes permitidos para embutir no prompt."""
    partes = []
    for nome in nomes:
        comp = COMPONENTES.get(nome)
        if not comp:
            raise ValueError(f"Componente desconhecido: {nome}. "
                             f"Válidos: {list(COMPONENTES)}")
        partes.append(f"- {nome}: {comp['descricao']}")
    return "\n".join(partes)


def _css_dos_componentes(nomes: list[str]) -> str:
    """Concatena o CSS dos componentes usados (+ base)."""
    css = TOKENS_CSS
    for nome in nomes:
        css += "\n" + COMPONENTES[nome]["css"]
    return css


SHELL_PROMPT_TMPL = """Você é um gerador de dashboards HTML para dados de treino e dieta.

REGRAS ABSOLUTAS:
1. Retorne APENAS o HTML completo, começando com <!DOCTYPE html>. Sem markdown,
   sem explicação antes ou depois.
2. Use EXATAMENTE os números dos dados fornecidos. Nunca invente ou arredonde
   valores além do que os dados trazem.
3. Use apenas os componentes listados abaixo, com as classes CSS indicadas.
   O CSS completo já está pronto (veja abaixo) — não escreva CSS próprio,
   exceto ajustes pontuais de layout (width/height de containers).
4. Gráficos: use ECharts via CDN https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js.
   Inicialize com echarts.init(document.querySelector('.chart')) e defina option
   com as cores das variáveis (--accent #4f8cff, --accent-2 #22c58b, --accent-3 #f4b942).
   Eixos: cor #8b91a5, gridlines sutis (#1f2330).
5. Página escura autocontida: <!DOCTYPE html>, <style> inline com o CSS fornecido,
   nenhum recurso externo além do CDN do ECharts.
6. Título claro relacionado ao pedido; insights curtos e objetivos.

COMPONENTES PERMITIDOS (use somente estes):
{paleta}

CSS PRONTO (cole dentro de <style>):
```css
{css}
```
"""


def montar_shell_prompt(componentes: list[str] | None = None) -> str:
    """Monta o system prompt do gerador para o subconjunto de componentes dado."""
    nomes = list(COMPONENTES) if componentes is None else componentes
    return SHELL_PROMPT_TMPL.format(
        paleta=_paleta_no_prompt(nomes),
        css=_css_dos_componentes(nomes),
    )


if __name__ == "__main__":
    print(montar_shell_prompt(["page_header", "metric_card", "line_chart"]))
    try:
        montar_shell_prompt(["gauge_3d"])
    except ValueError as e:
        print("\nOK — componente inválido rejeitado:", e)
