from dash import html, dcc, Input, Output
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime
import hashlib
import os


_PIPELINE_PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#7f7f7f',
]

_SECTOR_LABELS = {
    'sector-north': 'North',
    'sector-south': 'South',
}


def _pipeline_color(pipeline_id):
    digest = hashlib.md5(str(pipeline_id).encode()).hexdigest()
    return _PIPELINE_PALETTE[int(digest, 16) % len(_PIPELINE_PALETTE)]


def _percentile_range(values, lo_pct=0.02, hi_pct=0.98, pad_ratio=0.15, min_pad=1.0):
    finite = sorted(v for v in values if v is not None)
    if len(finite) < 2:
        return None
    n = len(finite)
    lo = finite[max(0, int(n * lo_pct))]
    hi = finite[min(n - 1, int(n * hi_pct))]
    pad = max((hi - lo) * pad_ratio, min_pad)
    return [lo - pad, hi + pad]


def _build_overview_chart(data_by_pid, sector_by_pid, y_title, fallback_range):
    fig = go.Figure()
    all_values = []

    for pid in sorted(data_by_pid.keys()):
        points = sorted(data_by_pid[pid], key=lambda d: d.get('timestamp') or '')
        if not points:
            continue
        xs = [d.get('timestamp') for d in points]
        ys = [d.get('value') for d in points]
        all_values.extend(v for v in ys if v is not None)

        sector_id = sector_by_pid.get(pid)
        sector_label = _SECTOR_LABELS.get(sector_id, sector_id or '—')
        trace_name = f"Pipeline {pid} ({sector_label})"

        fig.add_trace(go.Scatter(
            x=xs,
            y=ys,
            mode='lines',
            name=trace_name,
            line=dict(color=_pipeline_color(pid), width=2),
            hovertemplate='%{y:.1f}<extra>' + trace_name + '</extra>',
        ))

    yrange = _percentile_range(all_values) or fallback_range

    fig.update_layout(
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis_title="Time",
        yaxis_title=y_title,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='left',
            x=0,
            font=dict(size=10),
            bgcolor='rgba(0,0,0,0)',
        ),
        height=340,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#2c3e50', size=11),
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)', zeroline=False),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)',
            zeroline=False,
            range=yrange,
        ),
        hovermode='x unified',
    )
    return fig


def create_layout(service_client):
    return dbc.Container([
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.H2([
                        html.I(className="fas fa-tachometer-alt me-3",
                              style={'color': '#003576'}),
                        "System Overview"
                    ], className="mb-1",
                       style={'fontWeight': '700', 'color': '#2c3e50'}),
                    html.P("Real-time monitoring and system health dashboard",
                          className="text-muted",
                          style={'fontSize': '1rem', 'marginBottom': '0'})
                ], md=8),
                dbc.Col([
                    html.Div([
                        html.Label("Sector", style={'fontWeight': '500', 'color': '#2c3e50', 'fontSize': '0.85rem', 'marginBottom': '0.3rem'}),
                        dcc.Dropdown(
                            id='overview-sector-filter',
                            options=[],
                            value=None,
                            clearable=False,
                            placeholder="Loading sectors...",
                            style={'minWidth': '160px'}
                        )
                    ])
                ], md=4, className="d-flex align-items-center justify-content-end")
            ], className="mb-4")
        ]),

        html.Div(id="overview-stats", style={'marginBottom': '2rem'}),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-temperature-high me-2",
                                  style={'color': '#FF6B6B'}),
                            html.Span("Temperature Trends",
                                     style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="mb-3"),
                        dcc.Graph(id="overview-temp-chart",
                                 style={"height": "300px"},
                                 config={'displayModeBar': False})
                    ], style={'padding': '1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '15px',
                    'boxShadow': '0 4px 20px rgba(0,0,0,0.08)',
                    'border': '1px solid #f0f0f0'
                })
            ], md=6, className="mb-4 px-2"),
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-tachometer-alt me-2",
                                  style={'color': '#4ECDC4'}),
                            html.Span("Pressure Trends",
                                     style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="mb-3"),
                        dcc.Graph(id="overview-pressure-chart",
                                 style={"height": "300px"},
                                 config={'displayModeBar': False})
                    ], style={'padding': '1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '15px',
                    'boxShadow': '0 4px 20px rgba(0,0,0,0.08)',
                    'border': '1px solid #f0f0f0'
                })
            ], md=6, className="mb-4 px-2")
        ], className="g-0", style={'marginBottom': '1rem'}),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-server me-2",
                                  style={'color': '#003576'}),
                            html.Span("Service Status",
                                     style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="mb-3"),
                        html.Div(id="service-status-list")
                    ], style={'padding': '1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '15px',
                    'boxShadow': '0 4px 20px rgba(0,0,0,0.08)',
                    'border': '1px solid #f0f0f0'
                })
            ], md=6, className="mb-4 px-2"),
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-exclamation-triangle me-2",
                                  style={'color': '#FF6B6B'}),
                            html.Span("Recent Alerts",
                                     style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="mb-3"),
                        html.Div(id="recent-alerts-list")
                    ], style={'padding': '1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '15px',
                    'boxShadow': '0 4px 20px rgba(0,0,0,0.08)',
                    'border': '1px solid #f0f0f0'
                })
            ], md=6, className="mb-4 px-2")
        ], className="g-0"),

        dcc.Interval(
            id='overview-interval',
            interval=int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)),
            n_intervals=0
        )
    ], fluid=True, style={'padding': '2rem 1.5rem', 'maxWidth': '1400px'})

def register_callbacks(app, service_client):

    @app.callback(
        [Output('overview-sector-filter', 'options'),
         Output('overview-sector-filter', 'value')],
        [Input('auth-store', 'data')]
    )
    def update_overview_sector_options(auth_data):
        if not auth_data:
            raise PreventUpdate
        user = auth_data.get('user', {})
        user_id = user.get('id')
        role = user.get('role', 'viewer')
        options = service_client.get_sector_options_for_user(user_id, role)
        default_value = options[0]['value'] if options else None
        return options, default_value

    @app.callback(
        Output('overview-stats', 'children'),
        [Input('overview-interval', 'n_intervals'),
         Input('overview-sector-filter', 'value')]
    )
    def update_stats(n, sector_filter):
        pipelines = service_client.get_pipelines_by_sector(sector_filter)
        active_pipelines = sum(1 for p in pipelines if p.get('status') == 'active')
        total_pipelines = len(pipelines)

        avg_temp = None
        avg_pressure = None
        critical_count = 0
        warning_count = 0

        # Skip TSDB lookups entirely when no pipelines are registered — otherwise
        # the global aggregate query returns leftover history from prior runs.
        # 1h window keeps the presentation immune to data older than the talk.
        if pipelines:
            pid, bid = None, None
            if sector_filter and sector_filter != 'all':
                first = pipelines[0]
                pid = first['pipeline_id']
                bolts = first.get('bolts', [])
                if bolts:
                    bid = bolts[0] if isinstance(bolts[0], str) else bolts[0].get('bolt_id')
            statistics = service_client.get_statistics(pipeline_id=pid, bolt_id=bid, hours=1)
            avg_temp = statistics.get('temperature', {}).get('mean')
            avg_pressure = statistics.get('pressure', {}).get('mean')

            pipeline_ids = {p['pipeline_id'] for p in pipelines}
            all_anomalies = service_client.get_alerts(limit=100)
            anomalies = [a for a in all_anomalies if a.get('pipeline_id') in pipeline_ids]
            critical_count = sum(1 for a in anomalies if a.get('severity') == 'critical')
            warning_count = sum(1 for a in anomalies if a.get('severity') == 'warning')

        def _card(icon, color, label, value_content):
            return dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.Div([
                                html.I(className=icon, style={'fontSize': '2.5rem', 'color': color})
                            ], style={
                                'width': '70px', 'height': '70px', 'borderRadius': '15px',
                                'backgroundColor': f'{color}15',
                                'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'
                            }),
                            html.Div([
                                html.H6(label, className="mb-1",
                                       style={'color': '#7f8c8d', 'fontSize': '0.85rem', 'fontWeight': '500'}),
                                html.H3(value_content, className="mb-0",
                                       style={'fontWeight': '700', 'color': '#2c3e50'})
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ], style={'padding': '1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff', 'borderRadius': '15px',
                    'boxShadow': '0 4px 20px rgba(0,0,0,0.08)', 'border': '1px solid #f0f0f0',
                    'transition': 'transform 0.2s ease', 'height': '100%'
                })
            ], md=3, className="mb-3 px-2")

        alert_content = [
            dbc.Badge(str(critical_count), color="danger", className="me-1") if critical_count else None,
            dbc.Badge(str(warning_count), color="warning") if warning_count else None,
            "None" if (critical_count + warning_count) == 0 else ""
        ]

        stats = dbc.Row([
            _card("fas fa-project-diagram", "#4ECDC4", "Active Pipelines", f"{active_pipelines}/{total_pipelines}"),
            _card("fas fa-temperature-high", "#FF6B6B", "Avg Temperature", f"{avg_temp:.1f}°C" if avg_temp is not None else "-"),
            _card("fas fa-tachometer-alt", "#45B7D1", "Avg Pressure", f"{avg_pressure:.1f} PSI" if avg_pressure is not None else "-"),
            _card("fas fa-bell", '#FF6B6B' if critical_count > 0 else '#FFA502', "Active Alerts", alert_content)
        ], className="g-0")

        return stats

    @app.callback(
        [Output('overview-temp-chart', 'figure'),
         Output('overview-pressure-chart', 'figure')],
        [Input('overview-interval', 'n_intervals'),
         Input('overview-sector-filter', 'value')]
    )
    def update_charts(n, sector_filter):
        # Iterate per-pipeline (even on "All Sectors") so we never pull data for
        # pipelines that are no longer in the catalog. 1h window keeps the chart
        # immune to leftover writes from prior runs.
        sector_pipelines = service_client.get_pipelines_by_sector(sector_filter)

        temp_by_pid = {}
        pressure_by_pid = {}
        sector_by_pid = {}
        for p in sector_pipelines:
            pid = p['pipeline_id']
            sector_by_pid[pid] = p.get('location', {}).get('sector')
            for d in service_client.get_sensor_data('temperature', pipeline_id=pid, hours=1):
                temp_by_pid.setdefault(pid, []).append(d)
            for d in service_client.get_sensor_data('pressure', pipeline_id=pid, hours=1):
                pressure_by_pid.setdefault(pid, []).append(d)

        temp_fig = _build_overview_chart(temp_by_pid, sector_by_pid, "Temperature (°C)", [15, 50])
        pressure_fig = _build_overview_chart(pressure_by_pid, sector_by_pid, "Pressure (PSI)", [60, 130])

        return temp_fig, pressure_fig

    @app.callback(
        Output('service-status-list', 'children'),
        Input('overview-interval', 'n_intervals')
    )
    def update_service_status(n):
        services = service_client.get_services_status()

        if not services:
            return html.Div([
                html.I(className="fas fa-info-circle me-2", style={'color': '#95a5a6'}),
                html.Span("No service status available", style={'color': '#95a5a6'})
            ], className="text-center py-3")

        service_items = []
        for service in services[:10]:
            status = service.get('status', 'unknown')
            name = service.get('name', 'Unknown')
            icon_map = {
                'healthy': ('fas fa-check-circle', '#96CEB4'),
                'unhealthy': ('fas fa-exclamation-circle', '#FFA502'),
                'unreachable': ('fas fa-times-circle', '#FF6B6B'),
                'unknown': ('fas fa-question-circle', '#95a5a6')
            }
            icon_class, icon_color = icon_map.get(status, ('fas fa-question-circle', '#95a5a6'))

            service_items.append(
                html.Div([
                    html.Div([
                        html.I(className=icon_class,
                              style={'color': icon_color, 'fontSize': '1.1rem'}),
                        html.Span(name,
                                 style={'color': '#2c3e50', 'fontWeight': '500', 'fontSize': '0.9rem'}),
                        html.Span(status.upper(),
                                 style={
                                     'fontSize': '0.75rem',
                                     'fontWeight': '600',
                                     'color': icon_color,
                                     'backgroundColor': f'{icon_color}15',
                                     'padding': '0.2rem 0.6rem',
                                     'borderRadius': '8px'
                                 })
                    ], className="d-flex align-items-center justify-content-between gap-2")
                ], style={
                    'padding': '0.8rem',
                    'backgroundColor': '#f8f9fa',
                    'borderRadius': '10px',
                    'marginBottom': '0.5rem',
                    'border': '1px solid #e9ecef'
                })
            )

        return service_items

    @app.callback(
        Output('recent-alerts-list', 'children'),
        [Input('overview-interval', 'n_intervals'),
         Input('overview-sector-filter', 'value')]
    )
    def update_recent_alerts(n, sector_filter):
        if sector_filter and sector_filter != 'all':
            sector_pipelines = service_client.get_pipelines_by_sector(sector_filter)
            pipeline_ids = {p['pipeline_id'] for p in sector_pipelines}
            all_alerts = service_client.get_alerts(limit=20)
            alerts = [a for a in all_alerts if a.get('pipeline_id') in pipeline_ids][:5]
        else:
            alerts = service_client.get_alerts(limit=5)

        if not alerts:
            return html.Div([
                html.Div([
                    html.I(className="fas fa-check-circle",
                          style={'fontSize': '2rem', 'color': '#96CEB4', 'marginBottom': '0.5rem'}),
                    html.Div("All systems operating normally",
                            style={'color': '#2c3e50', 'fontWeight': '500'}),
                    html.Small("No recent alerts",
                              style={'color': '#95a5a6'})
                ], className="text-center py-4")
            ])

        alert_items = []
        for alert in alerts:
            severity = alert.get('severity', 'info')
            icon_map = {
                'critical': ('fas fa-exclamation-circle', '#FF6B6B', '#FFF5F5'),
                'warning': ('fas fa-exclamation-triangle', '#FFA502', '#FFF9F0'),
                'info': ('fas fa-info-circle', '#45B7D1', '#F0F9FF')
            }
            icon_class, border_color, bg_color = icon_map.get(severity, ('fas fa-info-circle', '#95a5a6', '#f8f9fa'))

            alert_items.append(
                html.Div([
                    html.Div([
                        html.I(className=icon_class,
                              style={'color': border_color, 'fontSize': '1.2rem', 'marginRight': '0.8rem'}),
                        html.Div([
                            html.Div([
                                html.Span(f"Pipeline {alert.get('pipeline_id', 'Unknown')}",
                                         style={'fontWeight': '600', 'color': '#2c3e50', 'fontSize': '0.9rem'}),
                                html.Span(f" • Bolt {alert.get('bolt_id', 'Unknown')}",
                                         style={'color': '#7f8c8d', 'fontSize': '0.85rem'})
                            ], className="mb-1"),
                            html.Div(alert.get('message', alert.get('anomaly_type', 'Alert')),
                                    style={'color': '#5a6c7d', 'fontSize': '0.85rem', 'lineHeight': '1.4'}),
                            html.Small(alert.get('timestamp', ''),
                                      style={'color': '#95a5a6', 'fontSize': '0.75rem'})
                        ], style={'flex': '1'})
                    ], className="d-flex align-items-start")
                ], style={
                    'padding': '0.9rem',
                    'backgroundColor': bg_color,
                    'borderRadius': '10px',
                    'marginBottom': '0.6rem',
                    'border': f'1px solid {border_color}30',
                    'borderLeft': f'4px solid {border_color}'
                })
            )

        return alert_items
