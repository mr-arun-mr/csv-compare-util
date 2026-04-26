"""Generates a self-contained HTML comparison report with trend charts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, BaseLoader

from .comparator import FileComparisonResult
from .history import load_history

# ---------------------------------------------------------------------------
# Jinja2 template
# ---------------------------------------------------------------------------

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>CSV Comparison Report</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"/>
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css"/>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
  <style>
    body { font-size: 0.875rem; }
    .nav-pills .nav-link.active { background-color: #0d6efd; }
    .metric-card { border-left: 4px solid #0d6efd; }
    .metric-card.green { border-color: #198754; }
    .metric-card.yellow { border-color: #ffc107; }
    .metric-card.red { border-color: #dc3545; }
    .cell-match { background-color: #d1e7dd !important; }
    .cell-mismatch { background-color: #f8d7da !important; }
    .cell-fuzzy { background-color: #fff3cd !important; }
    .row-missing { background-color: #fde8e8 !important; }
    .row-extra { background-color: #e8f4fd !important; }
    .pct-badge { font-size: 0.75rem; }
    .chart-container { position: relative; height: 280px; }
    pre.cell-val { white-space: pre-wrap; word-break: break-all; margin: 0; font-size: 0.75rem; }
    .tab-content { padding-top: 1rem; }
    .sticky-col { position: sticky; left: 0; background: #fff; z-index: 1; }
    table.dataTable thead th { white-space: nowrap; }
    .legend-box { display: inline-block; width: 14px; height: 14px; margin-right: 4px; vertical-align: middle; }
    .subtab-pane { display: none; }
    .subtab-pane.show { display: block; }
    .nav-tabs .nav-link { color: #495057; cursor: pointer; }
    .nav-tabs .nav-link.active { color: #0d6efd; font-weight: 600; }
  </style>
</head>
<body>
<div class="container-fluid py-3">

  <!-- Header -->
  <div class="d-flex align-items-center mb-3">
    <h4 class="mb-0 me-3">CSV Comparison Report</h4>
    <span class="text-muted small">Generated: {{ generated_at }}</span>
  </div>

  <!-- Top-level nav -->
  <ul class="nav nav-pills mb-3" id="mainTabs">
    <li class="nav-item">
      <a class="nav-link active" href="#summary" data-bs-toggle="pill">Summary &amp; Trends</a>
    </li>
    {% for r in results %}
    <li class="nav-item">
      <a class="nav-link" href="#file{{ loop.index }}" data-bs-toggle="pill">
        {{ r.expected_file | basename }}
      </a>
    </li>
    {% endfor %}
  </ul>

  <div class="tab-content">

    <!-- ====================================================== SUMMARY ===== -->
    <div class="tab-pane fade show active" id="summary">

      <!-- Metric cards -->
      <div class="row g-3 mb-4">
        <div class="col-6 col-md-3">
          <div class="card metric-card h-100 p-3">
            <div class="text-muted small">Files Compared</div>
            <div class="fs-3 fw-bold">{{ results | length }}</div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card metric-card {{ overall_pct | pct_class }} h-100 p-3">
            <div class="text-muted small">Overall Match</div>
            <div class="fs-3 fw-bold">{{ overall_pct | pct }}</div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card metric-card {{ row_pct | pct_class }} h-100 p-3">
            <div class="text-muted small">Row Match</div>
            <div class="fs-3 fw-bold">{{ row_pct | pct }}</div>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="card metric-card h-100 p-3">
            <div class="text-muted small">Total Rows (expected)</div>
            <div class="fs-3 fw-bold">{{ total_rows }}</div>
          </div>
        </div>
      </div>

      <!-- File summary table -->
      <h5 class="mb-2">File Summary</h5>
      <div class="table-responsive mb-4">
        <table class="table table-bordered table-sm table-hover" id="fileSummaryTable">
          <thead class="table-dark">
            <tr>
              <th>Expected File</th>
              <th>Actual File</th>
              <th>Expected Rows</th>
              <th>Actual Rows</th>
              <th>Matched Rows</th>
              <th>Row Match %</th>
              <th>Overall Match %</th>
            </tr>
          </thead>
          <tbody>
            {% for r in results %}
            <tr>
              <td>{{ r.expected_file | basename }}</td>
              <td>{{ r.actual_file | basename }}</td>
              <td>{{ r.total_expected }}</td>
              <td>{{ r.total_actual }}</td>
              <td>{{ r.matched_rows }}</td>
              <td><span class="badge {{ r.row_match_pct | pct_badge }}">{{ r.row_match_pct | pct }}</span></td>
              <td><span class="badge {{ r.overall_match_pct | pct_badge }}">{{ r.overall_match_pct | pct }}</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <!-- Trend charts -->
      {% if history | length > 1 %}
      <h5 class="mb-2">Trends <span class="text-muted small">(last {{ history | length }} runs)</span></h5>
      <div class="row g-3 mb-4">
        <div class="col-12 col-lg-6">
          <div class="card p-3">
            <div class="card-title small fw-bold">Overall &amp; Row Match %</div>
            <div class="chart-container"><canvas id="trendOverall"></canvas></div>
          </div>
        </div>
        <div class="col-12 col-lg-6">
          <div class="card p-3">
            <div class="card-title small fw-bold">Attribute Match % by Column</div>
            <div class="chart-container"><canvas id="trendAttr"></canvas></div>
          </div>
        </div>
      </div>
      {% endif %}

      <!-- Legend -->
      <div class="mb-3 small">
        <span class="legend-box" style="background:#d1e7dd;border:1px solid #aaa;"></span>Match&nbsp;&nbsp;
        <span class="legend-box" style="background:#fff3cd;border:1px solid #aaa;"></span>Fuzzy Match&nbsp;&nbsp;
        <span class="legend-box" style="background:#f8d7da;border:1px solid #aaa;"></span>Mismatch&nbsp;&nbsp;
        <span class="legend-box" style="background:#fde8e8;border:1px solid #aaa;"></span>Missing in Actual&nbsp;&nbsp;
        <span class="legend-box" style="background:#e8f4fd;border:1px solid #aaa;"></span>Extra in Actual
      </div>

    </div><!-- /summary -->

    <!-- ====================================================== PER-FILE ===== -->
    {% for r in results %}
    {% set fi = loop.index %}
    <div class="tab-pane fade" id="file{{ fi }}">
      <h5>{{ r.expected_file | basename }} vs {{ r.actual_file | basename }}</h5>

      <!-- File metrics -->
      <div class="row g-2 mb-3">
        {% set missing_count = r.rows | selectattr('status','eq','missing_in_actual') | list | length %}
        {% set extra_count   = r.rows | selectattr('status','eq','extra_in_actual')   | list | length %}
        {% set mismatch_rows = r.rows | selectattr('status','eq','compared') | rejectattr('row_match_pct','eq',100.0) | list | length %}
        {% set metrics = [
          ('Overall Match',    r.overall_match_pct),
          ('Row Match',        r.row_match_pct),
          ('Mismatched Rows',  mismatch_rows),
          ('Missing / Extra',  missing_count ~ ' / ' ~ extra_count),
        ] %}
        {% for label, val in metrics %}
        <div class="col-6 col-md-3">
          <div class="card p-2 text-center">
            <div class="text-muted" style="font-size:0.7rem">{{ label }}</div>
            <div class="fw-bold">
              {% if val is float %}{{ val | pct }}{% else %}{{ val }}{% endif %}
            </div>
          </div>
        </div>
        {% endfor %}
      </div>

      <!-- Attribute match chart -->
      {% if r.attribute_match_pcts %}
      <div class="card p-3 mb-3">
        <div class="card-title small fw-bold">Attribute Match %</div>
        <div class="chart-container"><canvas id="attrChart{{ fi }}"></canvas></div>
      </div>
      {% endif %}

      <!-- Sub-tabs: All Rows / Mismatch Detail -->
      <ul class="nav nav-tabs mb-2" id="subTabs{{ fi }}">
        <li class="nav-item">
          <a class="nav-link active" data-target="allRows{{ fi }}" data-subtab="{{ fi }}" href="#">All Rows</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" data-target="mismatchDetail{{ fi }}" data-subtab="{{ fi }}" href="#">
            Mismatch Detail
            <span class="badge bg-danger ms-1">{{ mismatch_rows + missing_count }}</span>
          </a>
        </li>
      </ul>

      <div class="subtab-content">

        <!-- ---- ALL ROWS tab ---- -->
        <div class="subtab-pane show active" id="allRows{{ fi }}">
          <!-- Filter buttons -->
          <div class="mb-2 d-flex gap-2 flex-wrap align-items-center">
            <span class="small text-muted me-1">Show:</span>
            <button class="btn btn-sm btn-outline-secondary row-filter-btn active" data-filter="all"    data-table="{{ fi }}">All</button>
            <button class="btn btn-sm btn-outline-danger   row-filter-btn"         data-filter="mismatch" data-table="{{ fi }}">Mismatches</button>
            <button class="btn btn-sm btn-outline-warning  row-filter-btn"         data-filter="missing"  data-table="{{ fi }}">Missing in Actual</button>
            <button class="btn btn-sm btn-outline-info     row-filter-btn"         data-filter="extra"    data-table="{{ fi }}">Extra in Actual</button>
          </div>
          <div class="table-responsive">
            <table class="table table-bordered table-sm" id="rowTable{{ fi }}" style="width:100%">
              <thead class="table-dark">
                <tr>
                  <th class="sticky-col">{{ r.row_key }}</th>
                  <th>Status</th>
                  <th>Row Match %</th>
                  {% for col in r.columns %}<th>{{ col }}</th>{% endfor %}
                </tr>
              </thead>
              <tbody>
                {% for row in r.rows %}
                {% set row_has_mismatch = (row.status == 'compared' and row.row_match_pct < 100.0) %}
                <tr class="{{ row.status | row_class }}"
                    data-row-status="{{ row.status }}"
                    data-row-mismatch="{{ 'true' if row_has_mismatch else 'false' }}">
                  <td class="sticky-col fw-bold">{{ row.key }}</td>
                  <td>
                    {% if row.status == 'compared' %}
                      <span class="badge bg-primary">compared</span>
                    {% elif row.status == 'missing_in_actual' %}
                      <span class="badge bg-danger">missing</span>
                    {% else %}
                      <span class="badge bg-info text-dark">extra</span>
                    {% endif %}
                  </td>
                  <td>
                    {% if row.status == 'compared' %}
                      <span class="badge {{ row.row_match_pct | pct_badge }}">{{ row.row_match_pct | pct }}</span>
                    {% else %}&mdash;{% endif %}
                  </td>
                  {% for col in r.columns %}
                  {% if row.status == 'compared' %}
                    {% set cell = row.cells[col] %}
                    <td class="{{ cell | cell_class }}">
                      {% if cell.match %}
                        <pre class="cell-val">{{ cell.expected }}</pre>
                      {% else %}
                        <pre class="cell-val text-danger fw-bold">{{ cell.expected }}</pre>
                        <pre class="cell-val text-primary">{{ cell.actual }}</pre>
                        {% if cell.similarity < 100.0 %}
                        <div class="pct-badge text-muted">sim: {{ cell.similarity | round(1) }}%</div>
                        {% endif %}
                      {% endif %}
                    </td>
                  {% elif row.status == 'missing_in_actual' %}
                    <td class="row-missing"><pre class="cell-val text-muted">—</pre></td>
                  {% else %}
                    <td class="row-extra"><pre class="cell-val text-muted">—</pre></td>
                  {% endif %}
                  {% endfor %}
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </div><!-- /allRows -->

        <!-- ---- MISMATCH DETAIL tab ---- -->
        <div class="subtab-pane" id="mismatchDetail{{ fi }}">
          {% set mismatch_entries = namespace(items=[]) %}
          {% for row in r.rows %}
            {% if row.status == 'missing_in_actual' %}
              {% set mismatch_entries.items = mismatch_entries.items + [(row.key, '__ROW__', 'missing_in_actual', '', '', 0)] %}
            {% elif row.status == 'extra_in_actual' %}
              {% set mismatch_entries.items = mismatch_entries.items + [(row.key, '__ROW__', 'extra_in_actual', '', '', 0)] %}
            {% elif row.status == 'compared' and row.row_match_pct < 100.0 %}
              {% for col in r.columns %}
                {% set cell = row.cells[col] %}
                {% if not cell.match %}
                  {% set mismatch_entries.items = mismatch_entries.items + [(row.key, col, 'cell_mismatch', cell.expected, cell.actual, cell.similarity)] %}
                {% endif %}
              {% endfor %}
            {% endif %}
          {% endfor %}

          {% if not mismatch_entries.items %}
          <div class="alert alert-success mt-2">No mismatches found — all compared rows match perfectly.</div>
          {% else %}
          <p class="text-muted small mb-2">
            {{ mismatch_entries.items | length }} discrepanc{{ 'y' if mismatch_entries.items | length == 1 else 'ies' }} found.
            <span class="legend-box ms-2" style="background:#f8d7da;border:1px solid #aaa;"></span>Expected&nbsp;
            <span class="legend-box" style="background:#cfe2ff;border:1px solid #aaa;"></span>Actual
          </p>
          <div class="table-responsive">
            <table class="table table-bordered table-sm" id="mismatchTable{{ fi }}" style="width:100%">
              <thead class="table-dark">
                <tr>
                  <th>{{ r.row_key }}</th>
                  <th>Column</th>
                  <th>Type</th>
                  <th style="background:#f8d7da;color:#333">Expected</th>
                  <th style="background:#cfe2ff;color:#333">Actual</th>
                  <th>Similarity</th>
                </tr>
              </thead>
              <tbody>
                {% for key, col, kind, exp_val, act_val, sim in mismatch_entries.items %}
                <tr>
                  <td class="fw-bold">{{ key }}</td>
                  {% if kind == 'missing_in_actual' %}
                  <td>—</td>
                  <td><span class="badge bg-danger">missing row</span></td>
                  <td class="row-missing text-muted">—</td>
                  <td class="row-missing text-muted">not present</td>
                  <td>—</td>
                  {% elif kind == 'extra_in_actual' %}
                  <td>—</td>
                  <td><span class="badge bg-info text-dark">extra row</span></td>
                  <td class="row-extra text-muted">not present</td>
                  <td class="row-extra text-muted">—</td>
                  <td>—</td>
                  {% else %}
                  <td>{{ col }}</td>
                  <td><span class="badge bg-warning text-dark">value mismatch</span></td>
                  <td class="cell-mismatch"><pre class="cell-val">{{ exp_val }}</pre></td>
                  <td style="background:#cfe2ff"><pre class="cell-val">{{ act_val }}</pre></td>
                  <td><span class="badge {{ sim | pct_badge }}">{{ sim | round(1) }}%</span></td>
                  {% endif %}
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          {% endif %}
        </div><!-- /mismatchDetail -->

      </div><!-- /subtab-content -->
    </div><!-- /file -->
    {% endfor %}

  </div><!-- /tab-content -->
</div><!-- /container -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
// ---- DataTables init ----
$(document).ready(function(){
  $('#fileSummaryTable').DataTable({ paging: false, searching: false, info: false });
  {% for r in results %}
  {% set fi = loop.index %}
  $('#rowTable{{ fi }}').DataTable({ pageLength: 25, scrollX: true });
  if ($('#mismatchTable{{ fi }}').length) {
    $('#mismatchTable{{ fi }}').DataTable({ pageLength: 50, scrollX: true });
  }
  {% endfor %}
});

// ---- Sub-tab switching (All Rows / Mismatch Detail) ----
document.querySelectorAll('.nav-tabs .nav-link[data-subtab]').forEach(function(link) {
  link.addEventListener('click', function(e) {
    e.preventDefault();
    var fi = this.getAttribute('data-subtab');
    var targetId = this.getAttribute('data-target');
    document.querySelectorAll('#subTabs' + fi + ' .nav-link').forEach(function(l){ l.classList.remove('active'); });
    document.querySelectorAll('#file' + fi + ' .subtab-pane').forEach(function(p){ p.classList.remove('show'); });
    this.classList.add('active');
    var pane = document.getElementById(targetId);
    if (pane) pane.classList.add('show');
  });
});

// ---- Row filter buttons ----
document.querySelectorAll('.row-filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var fi = this.getAttribute('data-table');
    var filter = this.getAttribute('data-filter');
    // toggle active style
    document.querySelectorAll('.row-filter-btn[data-table="' + fi + '"]').forEach(function(b){ b.classList.remove('active'); });
    this.classList.add('active');

    var dt = $('#rowTable' + fi).DataTable();
    dt.rows().every(function() {
      var tr = $(this.node());
      var status = tr.data('row-status');
      var hasMismatch = tr.data('row-mismatch') === true || tr.data('row-mismatch') === 'true';
      var show = false;
      if (filter === 'all') show = true;
      else if (filter === 'mismatch') show = (status === 'compared' && hasMismatch);
      else if (filter === 'missing')  show = (status === 'missing_in_actual');
      else if (filter === 'extra')    show = (status === 'extra_in_actual');
      tr.toggle(show);
    });
    dt.columns.adjust();
  });
});

// ---- Tab activation from pills ----
document.querySelectorAll('[data-bs-toggle="pill"]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('[data-bs-toggle="pill"]').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(x => { x.classList.remove('show','active'); });
    el.classList.add('active');
    const target = document.querySelector(el.getAttribute('href'));
    if(target){ target.classList.add('show','active'); }
  });
});

// ---- Per-file attribute bar charts ----
const CHART_COLORS = [
  '#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f',
  '#edc948','#b07aa1','#ff9da7','#9c755f','#bab0ac'
];
{% for r in results %}
{% if r.attribute_match_pcts %}
(function(){
  const labels = {{ r.attribute_match_pcts.keys() | list | tojson }};
  const data   = {{ r.attribute_match_pcts.values() | list | tojson }};
  const colors = data.map(v => v >= 90 ? '#198754' : v >= 70 ? '#ffc107' : '#dc3545');
  new Chart(document.getElementById('attrChart{{ loop.index }}'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Match %', data, backgroundColor: colors }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } }
    }
  });
})();
{% endif %}
{% endfor %}

// ---- Trend charts ----
{% if history | length > 1 %}
(function(){
  const history = {{ history | tojson }};
  const labels  = history.map(h => h.label);

  // Overall & row match trend
  new Chart(document.getElementById('trendOverall'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Overall Match %',
          data: history.map(h => h.overall_match_pct),
          borderColor: '#0d6efd', backgroundColor: 'rgba(13,110,253,0.1)',
          tension: 0.3, fill: true
        },
        {
          label: 'Row Match %',
          data: history.map(h => h.row_match_pct),
          borderColor: '#198754', backgroundColor: 'rgba(25,135,84,0.1)',
          tension: 0.3, fill: true
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } }
    }
  });

  // Attribute trend
  const allCols = [...new Set(history.flatMap(h => Object.keys(h.attribute_match_pcts)))];
  const attrDatasets = allCols.map((col, i) => ({
    label: col,
    data: history.map(h => h.attribute_match_pcts[col] ?? null),
    borderColor: CHART_COLORS[i % CHART_COLORS.length],
    tension: 0.3, fill: false, spanGaps: true
  }));
  new Chart(document.getElementById('trendAttr'), {
    type: 'line',
    data: { labels, datasets: attrDatasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } }
    }
  });
})();
{% endif %}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _pct_class(value: float) -> str:
    if value >= 90:
        return "green"
    if value >= 70:
        return "yellow"
    return "red"


def _pct_badge(value: float) -> str:
    if value >= 90:
        return "bg-success"
    if value >= 70:
        return "bg-warning text-dark"
    return "bg-danger"


def _basename(path: str) -> str:
    return Path(path).name


def _row_class(status: str) -> str:
    return {"missing_in_actual": "row-missing", "extra_in_actual": "row-extra"}.get(status, "")


def _cell_class(cell: Any) -> str:
    if cell.match and cell.similarity == 100.0:
        return "cell-match"
    if cell.match:
        return "cell-fuzzy"
    return "cell-mismatch"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    results: List[FileComparisonResult],
    output_dir: Path,
    run_label: str,
    include_history: bool = True,
) -> Path:
    history = load_history(output_dir) if include_history else []

    total_rows = sum(r.total_expected for r in results)
    matched_rows = sum(r.matched_rows for r in results)

    overall_pct = (
        sum(r.overall_match_pct * r.matched_rows for r in results) / matched_rows
        if matched_rows else 0.0
    )
    row_pct = (
        sum(r.row_match_pct * r.total_expected for r in results) / total_rows
        if total_rows else 0.0
    )

    env = Environment(loader=BaseLoader())
    env.filters["pct"] = _pct
    env.filters["pct_class"] = _pct_class
    env.filters["pct_badge"] = _pct_badge
    env.filters["basename"] = _basename
    env.filters["row_class"] = _row_class
    env.filters["cell_class"] = _cell_class
    env.filters["tojson"] = json.dumps

    template = env.from_string(_TEMPLATE)
    html = template.render(
        generated_at=run_label,
        results=results,
        history=history,
        overall_pct=overall_pct,
        row_pct=row_pct,
        total_rows=total_rows,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "comparison_report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path
