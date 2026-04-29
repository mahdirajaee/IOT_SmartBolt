from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from datetime import datetime
import os
from components.layouts import format_timestamp

def create_layout(service_client):
    refresh_seconds = max(int(int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)) / 1000), 1)
    return dbc.Container([
        html.Div([
            html.Div([
                html.Div([
                    html.Span("Command Center", style={'letterSpacing': '0.08em', 'color': '#9cc4ff', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-project-diagram me-3", style={'color': '#8be9fd'}),
                        "Pipeline Monitoring"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#ecf5ff'}),
                    html.P(
                        "Stay on top of each pipeline with real-time health, flow, and component visibility.",
                        className="mb-2",
                        style={'color': 'rgba(236,245,255,0.8)'}
                    ),
                    html.Div([
                        dbc.Badge("Live feed", color="success", className="me-2", pill=True),
                        dbc.Badge(
                            f"Auto refresh · {refresh_seconds}s",
                            color="info",
                            pill=True,
                            style={'backgroundColor': 'rgba(255,255,255,0.12)'}
                        )
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Stability", style={'color': '#cbd5e1', 'fontSize': '0.8rem'}),
                        html.H4("Pipelines", style={'color': '#ecf5ff', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Unified telemetry dashboard", style={'color': 'rgba(236,245,255,0.7)', 'fontSize': '0.9rem'})
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
                            html.Span("Select feed", style={'fontWeight': '700', 'color': '#0b1b2d', 'fontSize': '0.9rem'}),
                            html.P(
                                "Choose sector and pipeline to stream telemetry.",
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
                            html.Small("Live", style={'color': '#16a34a', 'fontWeight': '700'})
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
                                    id="pipelines-sector-filter",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    placeholder="Loading sectors...",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=4),
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-filter me-2", style={'color': '#0f3b63'}),
                                    html.Span("Select Pipeline", style={'fontWeight': '600', 'color': '#0b1b2d'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="pipeline-selector",
                                    placeholder="Choose a pipeline to monitor...",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=8)
                    ], className="g-3")
                ], style={'padding': '1.5rem'}),
                md=8,
                style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5',
                    'marginBottom': '1.25rem'
                }
            ),
            dbc.Col(
                html.Div(id="pipeline-status-badge"),
                md=4
            )
        ], className="g-3"),

        html.Div(id="pipeline-details", className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #fb7185, #fb923c)'}),
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-temperature-high me-2", style={'color': '#fb7185'}),
                            html.Span("Temperature Monitoring", style={'fontWeight': '700', 'color': '#0b1b2d'})
                        ], className="mb-3"),
                        dcc.Graph(id="pipeline-temp-chart", style={"height": "400px"}, config={'displayModeBar': False})
                    ], style={'padding': '1.25rem 1.5rem 1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5'
                })
            ], md=6, className="mb-4"),
            dbc.Col([
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #22d3ee, #4ade80)'}),
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-tachometer-alt me-2", style={'color': '#10b981'}),
                            html.Span("Pressure Monitoring", style={'fontWeight': '700', 'color': '#0b1b2d'})
                        ], className="mb-3"),
                        dcc.Graph(id="pipeline-pressure-chart", style={"height": "400px"}, config={'displayModeBar': False})
                    ], style={'padding': '1.25rem 1.5rem 1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5'
                })
            ], md=6, className="mb-4")
        ], className="g-3"),

        html.Div([
            html.Div([
                html.Div([
                    html.Div([
                        html.Div(
                            style={'width': '10px', 'height': '34px', 'borderRadius': '6px', 'background': 'linear-gradient(180deg, #0f3b63, #22c55e)'},
                            className="me-3"
                        ),
                        html.Div([
                            html.Div("Health Assessment", style={'fontWeight': '700', 'color': '#0b1b2d'}),
                            html.Div("Risk outlook and resilience score", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                        ])
                    ], className="d-flex align-items-center mb-3")
                ]),
                html.Div(id="pipeline-health")
            ], style={'padding': '1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5',
            'marginBottom': '1.5rem'
        }),

        dcc.Interval(
            id='pipelines-interval',
            interval=int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)),
            n_intervals=0
        )
    ], fluid=True, style={'padding': '2rem 1.25rem', 'backgroundColor': '#f6f8fb'})

def register_callbacks(app, service_client):

    @app.callback(
        [Output('pipelines-sector-filter', 'options'),
         Output('pipelines-sector-filter', 'value')],
        [Input('auth-store', 'data')]
    )
    def update_pipelines_sector_options(auth_data):
        if not auth_data:
            return [], None
        user = auth_data.get('user', {})
        user_id = user.get('id')
        role = user.get('role', 'viewer')
        options = service_client.get_sector_options_for_user(user_id, role)
        default_value = options[0]['value'] if options else None
        return options, default_value

    @app.callback(
        [Output('pipeline-selector', 'options'),
         Output('pipeline-selector', 'value')],
        [Input('pipelines-interval', 'n_intervals'),
         Input('pipelines-sector-filter', 'value')],
        [State('pipeline-selector', 'value')]
    )
    def update_pipeline_options(n, sector_filter, current_value):
        pipelines = service_client.get_pipelines_by_sector(sector_filter)

        options = [
            {'label': f"Pipeline {p['pipeline_id']} - {p.get('name', 'Unnamed')}",
             'value': p['pipeline_id']}
            for p in pipelines
        ]

        if current_value and any(opt['value'] == current_value for opt in options):
            return options, current_value
        elif options:
            return options, options[0]['value']
        return options, None

    @app.callback(
        [Output('pipeline-status-badge', 'children'),
         Output('pipeline-details', 'children')],
        [Input('pipeline-selector', 'value'),
         Input('pipelines-interval', 'n_intervals')]
    )
    def update_pipeline_info(pipeline_id, n):
        if not pipeline_id:
            return "", html.P("Select a pipeline to view details", className="text-muted")

        pipeline = service_client.get_pipeline(pipeline_id)
        if not pipeline:
            return "", html.P("Pipeline data not available", className="text-muted")

        status = pipeline.get('status', 'unknown')
        color = '#96CEB4' if status == 'active' else '#FF6B6B'

        status_badge = html.Div([
            html.Div([
                html.Div([
                    html.I(className="fas fa-circle",
                          style={'fontSize': '3rem', 'color': color}),
                ], style={
                    'width': '80px',
                    'height': '80px',
                    'borderRadius': '15px',
                    'backgroundColor': f'{color}15',
                    'display': 'flex',
                    'alignItems': 'center',
                    'justifyContent': 'center',
                    'margin': '0 auto 1rem auto'
                }),
                html.H5(status.upper(),
                       className="mb-0 text-center",
                       style={'fontWeight': '700', 'color': color})
            ], style={'padding': '1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '15px',
            'boxShadow': '0 4px 20px rgba(0,0,0,0.08)',
            'border': '1px solid #f0f0f0'
        })

        details = dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-map-marker-alt",
                                  style={'fontSize': '2rem', 'color': '#45B7D1'})
                        ], style={
                            'width': '60px',
                            'height': '60px',
                            'borderRadius': '12px',
                            'backgroundColor': '#45B7D115',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
                        html.Div([
                            html.H6("Location", className="mb-1",
                                   style={'color': '#7f8c8d', 'fontSize': '0.85rem'}),
                            html.H5(f"{pipeline.get('location', {}).get('sector', 'Unknown')}",
                                   className="mb-0",
                                   style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="ms-3")
                    ], className="d-flex align-items-center")
                ], style={'padding': '1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '12px',
                'boxShadow': '0 3px 15px rgba(0,0,0,0.06)',
                'border': '1px solid #f0f0f0'
            }, md=3),
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-bolt",
                                  style={'fontSize': '2rem', 'color': '#FFA502'})
                        ], style={
                            'width': '60px',
                            'height': '60px',
                            'borderRadius': '12px',
                            'backgroundColor': '#FFA50215',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
                        html.Div([
                            html.H6("Total Bolts", className="mb-1",
                                   style={'color': '#7f8c8d', 'fontSize': '0.85rem'}),
                            html.H5(str(len(pipeline.get('bolts', []))),
                                   className="mb-0",
                                   style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="ms-3")
                    ], className="d-flex align-items-center")
                ], style={'padding': '1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '12px',
                'boxShadow': '0 3px 15px rgba(0,0,0,0.06)',
                'border': '1px solid #f0f0f0'
            }, md=3),
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-cog",
                                  style={'fontSize': '2rem', 'color': '#96CEB4'})
                        ], style={
                            'width': '60px',
                            'height': '60px',
                            'borderRadius': '12px',
                            'backgroundColor': '#96CEB415',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
                        html.Div([
                            html.H6("Total Valves", className="mb-1",
                                   style={'color': '#7f8c8d', 'fontSize': '0.85rem'}),
                            html.H5(str(len(pipeline.get('valves', []))),
                                   className="mb-0",
                                   style={'fontWeight': '600', 'color': '#2c3e50'})
                        ], className="ms-3")
                    ], className="d-flex align-items-center")
                ], style={'padding': '1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '12px',
                'boxShadow': '0 3px 15px rgba(0,0,0,0.06)',
                'border': '1px solid #f0f0f0'
            }, md=3),
            dbc.Col([
                html.Div([
                    html.Div([
                        html.Div([
                            html.I(className="fas fa-clock",
                                  style={'fontSize': '2rem', 'color': '#4ECDC4'})
                        ], style={
                            'width': '60px',
                            'height': '60px',
                            'borderRadius': '12px',
                            'backgroundColor': '#4ECDC415',
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        }),
                        html.Div([
                            html.H6("Last Update", className="mb-1",
                                   style={'color': '#7f8c8d', 'fontSize': '0.85rem'}),
                            html.H6(format_timestamp(pipeline.get('last_update', 'Unknown')),
                                   className="mb-0",
                                   style={'fontWeight': '600', 'color': '#2c3e50', 'fontSize': '0.85rem'})
                        ], className="ms-3")
                    ], className="d-flex align-items-center")
                ], style={'padding': '1.2rem'})
            ], style={
                'backgroundColor': '#ffffff',
                'borderRadius': '12px',
                'boxShadow': '0 3px 15px rgba(0,0,0,0.06)',
                'border': '1px solid #f0f0f0'
            }, md=3)
        ])

        return status_badge, details

    @app.callback(
        [Output('pipeline-temp-chart', 'figure'),
         Output('pipeline-pressure-chart', 'figure')],
        [Input('pipeline-selector', 'value'),
         Input('pipelines-interval', 'n_intervals')]
    )
    def update_pipeline_charts(pipeline_id, n):
        if not pipeline_id:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                xaxis={"visible": False},
                yaxis={"visible": False},
                annotations=[{
                    "text": "Select a pipeline to view data",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20}
                }]
            )
            return empty_fig, empty_fig

        temp_data = service_client.get_sensor_data('temperature', pipeline_id=pipeline_id, hours=24)

        temp_fig = go.Figure()
        if temp_data:
            bolts = {}
            for d in temp_data:
                bolt_id = d.get('bolt_id', 'unknown')
                if bolt_id not in bolts:
                    bolts[bolt_id] = {'x': [], 'y': []}
                bolts[bolt_id]['x'].append(d['timestamp'])
                bolts[bolt_id]['y'].append(d['value'])

            for bolt_id, data in bolts.items():
                temp_fig.add_trace(go.Scatter(
                    x=data['x'],
                    y=data['y'],
                    mode='lines',
                    name=f"Bolt {bolt_id}"
                ))

        temp_fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Temperature (°C)",
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2c3e50', size=11),
            xaxis=dict(
                tickformat='%H:%M\n%b %d, %Y',
                type='date',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)'
            )
        )

        pressure_data = service_client.get_sensor_data('pressure', pipeline_id=pipeline_id, hours=24)

        pressure_fig = go.Figure()
        if pressure_data:
            bolts = {}
            for d in pressure_data:
                bolt_id = d.get('bolt_id', 'unknown')
                if bolt_id not in bolts:
                    bolts[bolt_id] = {'x': [], 'y': []}
                bolts[bolt_id]['x'].append(d['timestamp'])
                bolts[bolt_id]['y'].append(d['value'])

            for bolt_id, data in bolts.items():
                pressure_fig.add_trace(go.Scatter(
                    x=data['x'],
                    y=data['y'],
                    mode='lines',
                    name=f"Bolt {bolt_id}"
                ))

        pressure_fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Pressure (PSI)",
            hovermode='x unified',
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2c3e50', size=11),
            xaxis=dict(
                tickformat='%H:%M\n%b %d, %Y',
                type='date',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)'
            )
        )

        return temp_fig, pressure_fig

    @app.callback(
        Output('pipeline-health', 'children'),
        [Input('pipeline-selector', 'value'),
         Input('pipelines-interval', 'n_intervals')]
    )
    def update_pipeline_health(pipeline_id, n):
        if not pipeline_id:
            return html.P("Select a pipeline to view health assessment", className="text-muted")

        health = service_client.get_pipeline_health(pipeline_id)

        if not health:
            return html.P("Health data not available", className="text-muted")

        health_score = health.get('health_score', 0)
        risk_level = health.get('risk_level', 'unknown')
        risk_factors = health.get('risk_factors', [])

        if risk_level == 'high':
            color = 'danger'
        elif risk_level == 'medium':
            color = 'warning'
        else:
            color = 'success'

        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.H4("Health Score"),
                    dbc.Progress(
                        value=health_score,
                        label=f"{health_score}%",
                        color=color,
                        style={"height": "30px"},
                        className="mb-3"
                    )
                ], md=8),
                dbc.Col([
                    html.H4("Risk Level"),
                    dbc.Badge(risk_level.upper(), color=color, className="fs-3")
                ], md=4, className="text-center")
            ]),
            html.Hr(),
            html.H5("Risk Factors"),
            html.Ul([
                html.Li(factor) for factor in risk_factors
            ]) if risk_factors else html.P("No risk factors detected", className="text-muted")
        ])
