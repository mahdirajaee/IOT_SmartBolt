from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import os


def create_layout(service_client):
    refresh_seconds = max(int(int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)) * 2 / 1000), 1)
    return dbc.Container([
        html.Div([
            html.Div([
                html.Div([
                    html.Span("Incident Desk", style={'letterSpacing': '0.08em', 'color': '#ffb7b2', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-exclamation-triangle me-3", style={'color': '#ffd166'}),
                        "System Alerts"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#fff7ed'}),
                    html.P(
                        "Monitor anomalies across pipelines and respond quickly with filtered streams.",
                        className="mb-2",
                        style={'color': 'rgba(255,247,237,0.8)'}
                    ),
                    html.Div([
                        dbc.Badge(f"Polled · {refresh_seconds}s", color="danger", pill=True)
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Status", style={'color': '#ffe0d0', 'fontSize': '0.8rem'}),
                        html.H4("Alerts", style={'color': '#fff7ed', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Risk and incident cockpit", style={'color': 'rgba(255,247,237,0.7)', 'fontSize': '0.9rem'})
                    ], style={
                        'padding': '1rem 1.25rem',
                        'borderRadius': '12px',
                        'backgroundColor': 'rgba(255,255,255,0.08)',
                        'border': '1px solid rgba(255,255,255,0.1)'
                    })
                ], className="mt-3 mt-md-0")
            ], className="d-flex flex-wrap align-items-start justify-content-between gap-3")
        ], style={
            'background': 'linear-gradient(120deg, #2b0f1f 0%, #4d1b2e 50%, #1f0c17 100%)',
            'padding': '24px 26px',
            'borderRadius': '18px',
            'boxShadow': '0 22px 45px rgba(0,0,0,0.25)',
            'position': 'relative',
            'overflow': 'hidden',
            'marginBottom': '20px'
        }),

        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div([
                        html.Div([
                            html.Span("Filter stream", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.92rem'}),
                            html.P(
                                "Tune severity, pipeline, and volume for the feed.",
                                className="mb-0",
                                style={'color': '#6b7280', 'fontSize': '0.9rem'}
                            )
                        ], className="flex-grow-1")
                    ], className="d-flex align-items-start mb-3 gap-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-filter me-2", style={'color': '#be123c'}),
                                    html.Span("Severity", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="alert-severity-filter",
                                    options=[
                                        {'label': 'All', 'value': 'all'},
                                        {'label': 'Critical', 'value': 'critical'},
                                        {'label': 'Warning', 'value': 'warning'},
                                        {'label': 'Info', 'value': 'info'}
                                    ],
                                    value='all',
                                    clearable=False,
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=2),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-map-marker-alt me-2", style={'color': '#be123c'}),
                                    html.Span("Sector", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="alert-sector-filter",
                                    options=[],
                                    value=None,
                                    clearable=True,
                                    placeholder="All sectors",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=2),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-project-diagram me-2", style={'color': '#be123c'}),
                                    html.Span("Pipeline", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="alert-pipeline-filter",
                                    placeholder="All pipelines",
                                    clearable=True,
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=3),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-list-ol me-2", style={'color': '#be123c'}),
                                    html.Span("Limit", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="alert-limit-filter",
                                    options=[
                                        {'label': '25', 'value': 25},
                                        {'label': '50', 'value': 50},
                                        {'label': '100', 'value': 100},
                                        {'label': '200', 'value': 200}
                                    ],
                                    value=50,
                                    clearable=False,
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=2),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="fas fa-sync me-2"),
                                "Refresh"
                            ],
                                id="alert-refresh-btn",
                                style={'background': 'linear-gradient(135deg, #be123c 0%, #ef4444 100%)', 'border': 'none'},
                                className="mt-4 w-100"
                            )
                        ], md=1),
                        dbc.Col([
                            dbc.Button([
                                html.I(className="fas fa-times me-2"),
                                "Clear"
                            ],
                                id="alert-clear-btn",
                                color="secondary",
                                outline=True,
                                className="mt-4 w-100"
                            )
                        ], md=2)
                    ], className="g-3")
                ], style={'padding': '1.5rem'}),
                md=12,
                style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5',
                    'marginBottom': '1.25rem'
                }
            )
        ], className="g-3"),

        html.Div(id="alert-statistics", className="mb-4"),

        html.Div([
            html.Div([
                html.Div([
                    html.Div(
                        style={'width': '10px', 'height': '34px', 'borderRadius': '6px', 'background': 'linear-gradient(180deg, #be123c, #f97316)'},
                        className="me-3"
                    ),
                    html.Div([
                        html.Div("Alert History", style={'fontWeight': '700', 'color': '#0f172a'}),
                        html.Div("Stream of recent anomalies", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                    ], className="flex-grow-1"),
                    html.Div(id="alert-count", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                ], className="d-flex align-items-center mb-3 gap-2"),
                html.Div(id="alerts-list", style={"maxHeight": "620px", "overflowY": "auto"})
            ], style={'padding': '1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5'
        }),

        dcc.Interval(
            id='alerts-interval',
            interval=int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)) * 2,
            n_intervals=0
        )
    ], fluid=True, style={'padding': '2rem 1.25rem', 'backgroundColor': '#f6f8fb'})

def register_callbacks(app, service_client):

    @app.callback(
        Output('alert-sector-filter', 'options'),
        [Input('auth-store', 'data')]
    )
    def update_alert_sector_options(auth_data):
        if not auth_data:
            return []
        user = auth_data.get('user', {})
        user_id = user.get('id')
        role = user.get('role', 'viewer')
        return service_client.get_sector_options_for_user(user_id, role)

    @app.callback(
        Output('alert-pipeline-filter', 'options'),
        [Input('alerts-interval', 'n_intervals'),
         Input('alert-sector-filter', 'value')],
        [State('auth-store', 'data')]
    )
    def update_pipeline_options(n, sector_filter, auth_data):
        if not auth_data:
            return []

        user = auth_data.get('user', {})
        role = user.get('role', 'viewer')
        user_id = user.get('id')

        if sector_filter:
            pipelines = service_client.get_pipelines_by_sector(sector_filter)
        else:
            pipelines = service_client.get_pipelines()

        if role == 'admin':
            options = [
                {'label': f"Pipeline {p['pipeline_id']}", 'value': p['pipeline_id']}
                for p in pipelines
            ]
        else:
            user_sectors = service_client.get_user_sectors(user_id)
            options = [
                {'label': f"Pipeline {p['pipeline_id']}", 'value': p['pipeline_id']}
                for p in pipelines
                if p.get('location', {}).get('sector') in user_sectors
            ]

        return options

    @app.callback(
        [Output('alert-severity-filter', 'value'),
         Output('alert-sector-filter', 'value'),
         Output('alert-pipeline-filter', 'value'),
         Output('alert-limit-filter', 'value')],
        Input('alert-clear-btn', 'n_clicks'),
        prevent_initial_call=True
    )
    def clear_filters(n_clicks):
        return 'all', None, None, 50

    @app.callback(
        [Output('alerts-list', 'children'),
         Output('alert-count', 'children'),
         Output('alert-statistics', 'children')],
        [Input('alert-refresh-btn', 'n_clicks'),
         Input('alerts-interval', 'n_intervals'),
         Input('alert-severity-filter', 'value'),
         Input('alert-pipeline-filter', 'value'),
         Input('alert-limit-filter', 'value')]
    )
    def update_alerts(refresh_clicks, n_intervals, severity, pipeline_id, limit):

        all_alerts = service_client.get_alerts(
            pipeline_id=pipeline_id,
            limit=limit if limit else 50
        )

        if severity and severity != 'all':
            alerts = [a for a in all_alerts if a.get('severity') == severity]
        else:
            alerts = all_alerts

        critical_count = sum(1 for a in all_alerts if a.get('severity') == 'critical')
        warning_count = sum(1 for a in all_alerts if a.get('severity') == 'warning')
        info_count = sum(1 for a in all_alerts if a.get('severity') == 'info')

        def _stat_card(icon, icon_color, bg_color, gradient, label, count):
            return dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': gradient}),
                    html.Div([
                        html.Div([
                            html.Div([
                                html.I(className=icon, style={'fontSize': '2rem', 'color': icon_color})
                            ], style={
                                'width': '60px', 'height': '60px', 'borderRadius': '12px',
                                'backgroundColor': bg_color,
                                'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'
                            }),
                            html.Div([
                                html.H6(label, className="mb-1",
                                       style={'color': '#6b7280', 'fontSize': '0.85rem', 'fontWeight': '500'}),
                                html.H3(str(count), className="mb-0",
                                       style={'fontWeight': '700', 'color': icon_color})
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ], style={'padding': '1.25rem 1.25rem 1.35rem'})
                ], style={
                    'backgroundColor': '#ffffff', 'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)', 'border': '1px solid #e6ecf5'
                })
            ], md=3)

        stats = dbc.Row([
            _stat_card("fas fa-exclamation-circle", "#ef4444", "#fee2e2",
                      "linear-gradient(90deg, #ef4444, #f97316)", "Critical", critical_count),
            _stat_card("fas fa-exclamation-triangle", "#f59e0b", "#fef3c7",
                      "linear-gradient(90deg, #f97316, #facc15)", "Warning", warning_count),
            _stat_card("fas fa-info-circle", "#0ea5e9", "#e0f2fe",
                      "linear-gradient(90deg, #0ea5e9, #22d3ee)", "Info", info_count),
            _stat_card("fas fa-list", "#0f172a", "#e2e8f0",
                      "linear-gradient(90deg, #0f172a, #334155)", "Total", len(all_alerts))
        ], className="g-3")

        if not alerts:
            alerts_content = dbc.Alert(
                "No alerts found with the current filters",
                color="info"
            )
        else:
            alerts_content = []
            for alert in alerts:
                severity = alert.get('severity', 'info')
                color_map = {
                    'critical': 'danger',
                    'warning': 'warning',
                    'info': 'info'
                }
                color = color_map.get(severity, 'secondary')

                try:
                    timestamp = datetime.fromisoformat(alert.get('timestamp', ''))
                    time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = alert.get('timestamp', 'Unknown')

                tone_map = {
                    'critical': '#ef4444',
                    'warning': '#f59e0b',
                    'info': '#0ea5e9'
                }
                tone = tone_map.get(severity, '#0f172a')

                alert_card = html.Div([
                    html.Div([
                        html.Div([
                            dbc.Badge(severity.upper(), color=color, className="me-2"),
                            html.Span(f"Pipeline {alert.get('pipeline_id', 'Unknown')}"),
                            html.Span(f" • Bolt {alert.get('bolt_id', 'Unknown')}", className="ms-1 text-muted")
                        ], className="d-flex align-items-center flex-wrap gap-1"),
                        html.Small(time_str, className="text-muted")
                    ], className="d-flex align-items-start justify-content-between mb-2"),
                    html.P(alert.get('message', 'No message'), className="mb-1", style={'color': '#0f172a', 'fontWeight': '600'}),
                    html.Small([
                        f"Type: {alert.get('anomaly_type', 'Unknown')} | ",
                        f"Value: {alert.get('value', 'N/A')}"
                    ], className="text-muted")
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '12px',
                    'border': f'1px solid {tone}33',
                    'borderLeft': f'4px solid {tone}',
                    'padding': '1rem 1.1rem',
                    'boxShadow': '0 10px 24px rgba(15,23,42,0.06)',
                    'marginBottom': '0.85rem'
                })

                alerts_content.append(alert_card)

        alert_count = f"Showing {len(alerts)} of {len(all_alerts)} alerts"

        return alerts_content, alert_count, stats
