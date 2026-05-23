from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime
import pandas as pd
import os


def _factor_tone(weight):
    try:
        w = float(weight or 0)
    except (TypeError, ValueError):
        w = 0
    if w >= 0.3:
        return "danger"
    if w >= 0.2:
        return "warning"
    return "info"


def _trend_visual(trend_label):
    table = {
        'rapidly_increasing': ('fas fa-arrow-up', '#dc2626'),
        'increasing': ('fas fa-arrow-up', '#f97316'),
        'stable': ('fas fa-equals', '#6b7280'),
        'decreasing': ('fas fa-arrow-down', '#3b82f6'),
        'rapidly_decreasing': ('fas fa-arrow-down', '#06b6d4'),
    }
    return table.get(trend_label, ('fas fa-circle-question', '#94a3b8'))


def create_layout(service_client):
    return dbc.Container([
        html.Div([
            html.Div([
                html.Div([
                    html.Span("Insight Lab", style={'letterSpacing': '0.08em', 'color': '#b6d0ff', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-chart-line me-3", style={'color': '#8be9fd'}),
                        "Analytics & Insights"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#ecf5ff'}),
                    html.P(
                        "Deep dive into telemetry trends, anomaly mix, and predictive signals across pipelines.",
                        className="mb-2",
                        style={'color': 'rgba(236,245,255,0.82)'}
                    ),
                    html.Div([
                        dbc.Badge("Exploratory", color="info", className="me-2", pill=True),
                        dbc.Badge("Correlation + Predictive", color="light", pill=True, style={'backgroundColor': 'rgba(255,255,255,0.16)', 'color': '#ecf5ff'})
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Mode", style={'color': '#cbd5e1', 'fontSize': '0.8rem'}),
                        html.H4("Analytics", style={'color': '#ecf5ff', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Aggregate + prediction suite", style={'color': 'rgba(236,245,255,0.7)', 'fontSize': '0.9rem'})
                    ], style={
                        'padding': '1rem 1.25rem',
                        'borderRadius': '12px',
                        'backgroundColor': 'rgba(255,255,255,0.08)',
                        'border': '1px solid rgba(255,255,255,0.08)'
                    })
                ], className="mt-3 mt-md-0")
            ], className="d-flex flex-wrap align-items-start justify-content-between gap-3")
        ], style={
            'background': 'linear-gradient(120deg, #0b1f3a 0%, #0f3b63 50%, #0b1b2d 100%)',
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
                            html.Span("Select scope", style={'fontWeight': '700', 'color': '#0b1b2d', 'fontSize': '0.92rem'}),
                            html.P(
                                "Focus sector, pipeline, and horizon for analytics.",
                                className="mb-0",
                                style={'color': '#6b7280', 'fontSize': '0.9rem'}
                            )
                        ], className="flex-grow-1"),
                        html.Div([
                            html.Div(
                                style={
                                    'width': '10px',
                                    'height': '10px',
                                    'borderRadius': '50%',
                                    'backgroundColor': '#22c55e'
                                },
                                className="me-2"
                            ),
                            html.Small("Ready", style={'color': '#16a34a', 'fontWeight': '700'})
                        ], className="d-flex align-items-center")
                    ], className="d-flex align-items-start justify-content-between mb-3 gap-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-map-marker-alt me-2", style={'color': '#0f3b63'}),
                                    html.Span("Sector", style={'fontWeight': '600', 'color': '#0b1b2d'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="analytics-sector-filter",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    placeholder="Loading sectors...",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=3),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-project-diagram me-2", style={'color': '#0f3b63'}),
                                    html.Span("Pipeline", style={'fontWeight': '600', 'color': '#0b1b2d'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="analytics-pipeline-selector",
                                    placeholder="Select pipeline for analysis...",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=4),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-clock me-2", style={'color': '#0f3b63'}),
                                    html.Span("Time Range", style={'fontWeight': '600', 'color': '#0b1b2d'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="analytics-time-range",
                                    options=[
                                        {'label': 'Last Hour', 'value': 1},
                                        {'label': 'Last 6 Hours', 'value': 6},
                                        {'label': 'Last 24 Hours', 'value': 24},
                                        {'label': 'Last 7 Days', 'value': 168},
                                        {'label': 'Last 30 Days', 'value': 720}
                                    ],
                                    value=24,
                                    clearable=False,
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=3),
                        dbc.Col([
                            dbc.Button(
                                "Generate Analysis",
                                id="analytics-generate-btn",
                                style={'background': 'linear-gradient(135deg, #0f3b63 0%, #22c55e 100%)', 'border': 'none'},
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

        html.Div(id="analytics-metrics", className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #22d3ee, #6366f1)'}),
                    html.Div([
                        html.Div("Temperature vs Pressure Correlation", style={'fontWeight': '700', 'color': '#0b1b2d'}),
                        dcc.Graph(id="correlation-chart", style={"height": "400px"})
                    ], style={'padding': '1.25rem 1.5rem 1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5'
                })
            ], md=6),
            dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #f97316, #facc15)'}),
                    html.Div([
                        html.Div("Anomaly Distribution", style={'fontWeight': '700', 'color': '#0b1b2d'}),
                        dcc.Graph(id="anomaly-distribution", style={"height": "400px"})
                    ], style={'padding': '1.25rem 1.5rem 1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5'
                })
            ], md=6)
        ], className="mb-4 g-3"),

        html.Div([
            html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #0f3b63, #22c55e)'}),
            html.Div([
                html.Div("Predictive Analysis", style={'fontWeight': '700', 'color': '#0b1b2d', 'marginBottom': '0.5rem'}),
                html.Div(id="predictions-content")
            ], style={'padding': '1.25rem 1.5rem 1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5',
            'marginBottom': '1.25rem'
        }),

        html.Div([
            html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #10b981, #22d3ee)'}),
            html.Div([
                html.Div("Sensor Activity Heatmap", style={'fontWeight': '700', 'color': '#0b1b2d', 'marginBottom': '0.5rem'}),
                dcc.Graph(id="activity-heatmap", style={"height": "500px"})
            ], style={'padding': '1.25rem 1.5rem 1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5'
        })
    ], fluid=True, style={'padding': '2rem 1.25rem', 'backgroundColor': '#f6f8fb'})

def register_callbacks(app, service_client):

    @app.callback(
        [Output('analytics-sector-filter', 'options'),
         Output('analytics-sector-filter', 'value')],
        [Input('auth-store', 'data')]
    )
    def update_analytics_sector_options(auth_data):
        if not auth_data:
            return [], None
        user = auth_data.get('user', {})
        user_id = user.get('id')
        role = user.get('role', 'viewer')
        options = service_client.get_sector_options_for_user(user_id, role)
        default_value = options[0]['value'] if options else None
        return options, default_value

    @app.callback(
        Output('analytics-pipeline-selector', 'options'),
        [Input('analytics-sector-filter', 'value')]
    )
    def update_pipeline_options(sector_filter):
        pipelines = service_client.get_pipelines_by_sector(sector_filter)
        options = [
            {'label': f"Pipeline {p['pipeline_id']} - {p.get('name', 'Unnamed')}",
             'value': p['pipeline_id']}
            for p in pipelines
        ]
        return options

    @app.callback(
        Output('analytics-metrics', 'children'),
        [Input('analytics-generate-btn', 'n_clicks')],
        [State('analytics-pipeline-selector', 'value'),
         State('analytics-time-range', 'value')]
    )
    def update_metrics(n_clicks, pipeline_id, hours):
        if not pipeline_id:
            return dbc.Alert("Please select a pipeline for analysis", color="info")

        pipeline_details = service_client.get_pipeline(pipeline_id)
        bid = None
        if pipeline_details:
            bolts = pipeline_details.get('bolts', [])
            if bolts:
                bid = bolts[0].get('bolt_id') if isinstance(bolts[0], dict) else bolts[0]
        stats = service_client.get_statistics(pipeline_id=pipeline_id, bolt_id=bid)
        trend = service_client.get_trend(pipeline_id, bid)

        health = service_client.get_pipeline_health(pipeline_id)
        health_score = health.get('health_score', 0) if health else 0
        risk_score = health.get('risk_score', 0) if health else 0
        risk_level = health.get('risk_level', 'unknown') if health else 'unknown'
        risk_factors = health.get('risk_factors', []) if health else []

        anomalies = service_client.get_alerts(pipeline_id=pipeline_id, limit=1000)
        anomaly_rate = len(anomalies) / max(hours, 1)

        def _sensor_card(label, gradient, sensor_key, value_fmt):
            s = stats.get(sensor_key) or {}
            t = trend.get(sensor_key) or {}

            mean = s.get('mean', 0) or 0
            sigma = s.get('std_dev', 0) or 0
            median = s.get('median')
            iqr = s.get('iqr')
            p25 = s.get('percentile_25')
            p75 = s.get('percentile_75')

            trend_label = t.get('trend') or 'insufficient_data'
            slope = t.get('slope', 0) or 0
            r2_pct = t.get('confidence', 0) or 0
            icon_cls, tone = _trend_visual(trend_label)

            children = [
                html.Div(label, style={'color': '#6b7280', 'fontSize': '0.9rem', 'fontWeight': '600'}),
                html.H3(value_fmt(mean), style={'marginBottom': '0.25rem', 'color': '#0b1b2d', 'fontWeight': '700'}),
                html.Small(f"σ = {sigma:.2f}", style={'color': '#94a3b8'}),
            ]

            if median is not None and iqr is not None and p25 is not None and p75 is not None:
                children.append(html.Div(
                    f"median {median:.2f} · IQR {iqr:.2f} (p25 {p25:.1f} – p75 {p75:.1f})",
                    style={'color': '#94a3b8', 'fontSize': '0.78rem', 'marginTop': '0.4rem'}
                ))

            if trend_label not in ('insufficient_data', 'undefined'):
                children.append(html.Div([
                    html.I(className=f"{icon_cls} me-2", style={'color': tone}),
                    html.Span(f"trend: {trend_label.replace('_', ' ')}",
                              style={'color': tone, 'fontWeight': '700', 'fontSize': '0.8rem'}),
                    html.Span(f"  (slope {slope:+.3f}, R² {r2_pct/100:.2f})",
                              style={'color': '#94a3b8', 'fontSize': '0.75rem'}),
                ], style={'marginTop': '0.45rem'}))

            return dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': gradient}),
                    html.Div(children, style={'padding': '1.1rem 1.25rem 1.2rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5'
                })
            ], md=3)

        temp_card = _sensor_card(
            "Avg Temperature",
            'linear-gradient(90deg, #22d3ee, #38bdf8)',
            'temperature',
            lambda v: f"{v:.1f}°C",
        )
        pressure_card = _sensor_card(
            "Avg Pressure",
            'linear-gradient(90deg, #6366f1, #22d3ee)',
            'pressure',
            lambda v: f"{v:.1f} PSI",
        )

        factor_chips = [
            dbc.Badge(
                (f.get('factor', '?') if isinstance(f, dict) else str(f)).replace('_', ' '),
                color=_factor_tone(f.get('weight', 0) if isinstance(f, dict) else 0),
                className="me-1 mb-1",
                pill=True,
            )
            for f in risk_factors
        ]

        try:
            risk_score_num = float(risk_score or 0)
        except (TypeError, ValueError):
            risk_score_num = 0

        health_card_children = [
            html.Div("Health Score", style={'color': '#6b7280', 'fontSize': '0.9rem', 'fontWeight': '600'}),
            html.Div([
                html.H3(f"{health_score}%", style={'marginBottom': '0', 'color': '#0b1b2d', 'fontWeight': '700'}),
                dbc.Badge(
                    risk_level.upper(),
                    color="danger" if risk_level in ("high", "critical") else "warning" if risk_level == "medium" else "success",
                    className="ms-2"
                )
            ], className="d-flex align-items-center mt-1"),
            html.Div([
                html.Span("Risk ", style={'color': '#6b7280', 'fontSize': '0.78rem'}),
                html.Span(f"{risk_score_num:.0f} / 100",
                          style={'color': '#0b1b2d', 'fontWeight': '700', 'fontSize': '0.85rem'}),
            ], style={'marginTop': '0.45rem'}),
        ]
        if factor_chips:
            health_card_children.append(html.Div(factor_chips, style={'marginTop': '0.4rem'}))

        health_card = dbc.Col([
            html.Div([
                html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #0ea5e9, #22c55e)'}),
                html.Div(health_card_children, style={'padding': '1.1rem 1.25rem 1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '14px',
                'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                'border': '1px solid #e6ecf5'
            })
        ], md=3)

        anomaly_card = dbc.Col([
            html.Div([
                html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #f97316, #ef4444)'}),
                html.Div([
                    html.Div("Anomaly Rate", style={'color': '#6b7280', 'fontSize': '0.9rem', 'fontWeight': '600'}),
                    html.H3(f"{anomaly_rate:.2f}/hr", style={'marginBottom': '0.25rem', 'color': '#0b1b2d', 'fontWeight': '700'}),
                    html.Small(f"Total: {len(anomalies)}", style={'color': '#94a3b8'})
                ], style={'padding': '1.1rem 1.25rem 1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '14px',
                'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                'border': '1px solid #e6ecf5'
            })
        ], md=3)

        return dbc.Row([temp_card, pressure_card, health_card, anomaly_card], className="g-3")

    @app.callback(
        [Output('correlation-chart', 'figure'),
         Output('anomaly-distribution', 'figure')],
        [Input('analytics-generate-btn', 'n_clicks')],
        [State('analytics-pipeline-selector', 'value'),
         State('analytics-time-range', 'value')]
    )
    def update_correlation_charts(n_clicks, pipeline_id, hours):
        if not pipeline_id:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="Select a pipeline to view analytics",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return empty_fig, empty_fig

        temp_data = service_client.get_sensor_data('temperature', pipeline_id=pipeline_id, hours=hours)
        pressure_data = service_client.get_sensor_data('pressure', pipeline_id=pipeline_id, hours=hours)

        corr_fig = go.Figure()
        if temp_data and pressure_data:
            temp_dict = {d['timestamp']: d['value'] for d in temp_data}
            matched_data = []
            for p in pressure_data:
                if p['timestamp'] in temp_dict:
                    matched_data.append({
                        'temp': temp_dict[p['timestamp']],
                        'pressure': p['value']
                    })

            if matched_data:
                corr_fig.add_trace(go.Scatter(
                    x=[d['temp'] for d in matched_data],
                    y=[d['pressure'] for d in matched_data],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=[d['pressure'] for d in matched_data],
                        colorscale='Viridis',
                        showscale=True
                    ),
                    text=[f"T: {d['temp']:.1f}°C<br>P: {d['pressure']:.1f} PSI"
                          for d in matched_data],
                    hovertemplate='%{text}<extra></extra>'
                ))

        corr_fig.update_layout(
            xaxis_title="Temperature (°C)",
            yaxis_title="Pressure (PSI)",
            showlegend=False,
            height=400
        )

        anomalies = service_client.get_alerts(pipeline_id=pipeline_id, limit=1000)

        if anomalies:
            anomaly_types = {}
            for a in anomalies:
                atype = a.get('anomaly_type', 'Unknown')
                anomaly_types[atype] = anomaly_types.get(atype, 0) + 1

            dist_fig = go.Figure(data=[
                go.Pie(
                    labels=list(anomaly_types.keys()),
                    values=list(anomaly_types.values()),
                    hole=0.3
                )
            ])
        else:
            dist_fig = go.Figure()
            dist_fig.add_annotation(
                text="No anomalies detected",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )

        dist_fig.update_layout(height=400)

        return corr_fig, dist_fig

    @app.callback(
        Output('predictions-content', 'children'),
        [Input('analytics-generate-btn', 'n_clicks')],
        [State('analytics-pipeline-selector', 'value')]
    )
    def update_predictions(n_clicks, pipeline_id):
        if not pipeline_id:
            return html.P("Select a pipeline to view predictions", className="text-muted")

        predictions = service_client.get_predictions(pipeline_id)

        if not predictions or not predictions.get('predictions'):
            return dbc.Alert("No predictions available for this pipeline", color="info")

        pred_list = predictions.get('predictions', [])

        pred_cards = []
        for pred in pred_list[:5]:
            confidence = pred.get('confidence', 0) * 100
            pred_type = pred.get('type', 'Unknown')
            timeframe = pred.get('timeframe', 'Unknown')
            description = pred.get('description', 'No description')

            color = 'danger' if confidence > 75 else 'warning' if confidence > 50 else 'info'
            tone_map = {
                'danger': '#ef4444',
                'warning': '#f59e0b',
                'info': '#0ea5e9'
            }
            tone = tone_map.get(color, '#0b1b2d')

            pred_cards.append(
                html.Div([
                    html.Div([
                        html.Div([
                            html.Div(pred_type, style={'fontWeight': '700', 'color': '#0b1b2d'}),
                            html.Small(f"Timeframe: {timeframe}", className="text-muted")
                        ], className="d-flex flex-column"),
                        html.Div([
                            dbc.Progress(
                                value=confidence,
                                label=f"{confidence:.0f}%",
                                color=color,
                                style={"height": "20px", 'fontSize': '0.8rem'}
                            ),
                            html.Small("Confidence", className="text-muted")
                        ], className="text-end")
                    ], className="d-flex align-items-start justify-content-between mb-2 flex-wrap gap-2"),
                    html.Div(description, style={'color': '#0f172a', 'marginBottom': '0.35rem'}),
                    html.Small(pred.get('additional', ''), className="text-muted") if pred.get('additional') else None
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '12px',
                    'border': f'1px solid {tone}33',
                    'borderLeft': f'4px solid {tone}',
                    'padding': '1rem 1.1rem',
                    'boxShadow': '0 10px 24px rgba(15,23,42,0.06)',
                    'marginBottom': '0.8rem'
                })
            )

        return html.Div(pred_cards)

    @app.callback(
        Output('activity-heatmap', 'figure'),
        [Input('analytics-generate-btn', 'n_clicks')],
        [State('analytics-pipeline-selector', 'value'),
         State('analytics-time-range', 'value')]
    )
    def update_heatmap(n_clicks, pipeline_id, hours):
        if not pipeline_id:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="Select a pipeline to view activity heatmap",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return empty_fig

        temp_data = service_client.get_sensor_data('temperature', pipeline_id=pipeline_id, hours=hours)

        if not temp_data:
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="No data available for heatmap",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return empty_fig

        df_data = []
        for d in temp_data:
            try:
                timestamp = datetime.fromisoformat(d['timestamp'])
                df_data.append({
                    'bolt': d.get('bolt_id', 'Unknown'),
                    'hour': timestamp.hour,
                    'value': d['value']
                })
            except:
                continue

        if df_data:
            df = pd.DataFrame(df_data)
            pivot = df.pivot_table(values='value', index='bolt', columns='hour', aggfunc='mean')

            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=[f"{h:02d}:00" for h in pivot.columns],
                y=pivot.index,
                colorscale='RdYlBu_r',
                colorbar=dict(title="Temp (°C)")
            ))

            fig.update_layout(
                xaxis_title="Hour of Day",
                yaxis_title="Sensor Bolt",
                height=500
            )
        else:
            fig = go.Figure()
            fig.add_annotation(
                text="Insufficient data for heatmap",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )

        return fig
