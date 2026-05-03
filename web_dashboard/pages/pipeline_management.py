from dash import html, dcc, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import json
from typing import Dict, List
from datetime import datetime
from components.layouts import format_timestamp



def create_layout(service_client):
    refresh_seconds = max(int(30000 / 1000), 1)
    return dbc.Container([
        dcc.Store(id='pipeline-bundles-store', data={}),
        dcc.Interval(id='pipeline-bundles-interval', interval=30000, n_intervals=0),

        html.Div([
            html.Div([
                html.Div([
                    html.Span("Config Suite", style={'letterSpacing': '0.08em', 'color': '#b6d0ff', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-tools me-3", style={'color': '#8be9fd'}),
                        "Pipeline Management"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#ecf5ff'}),
                    html.P(
                        "Create, edit, and retire pipeline bundles with full component context.",
                        className="mb-2",
                        style={'color': 'rgba(236,245,255,0.82)'}
                    ),
                    html.Div([
                        dbc.Badge("Admin only", color="danger", className="me-2", pill=True),
                        dbc.Badge(f"Auto refresh · {refresh_seconds}s", pill=True,
                                  style={'backgroundColor': 'rgba(99,102,241,0.25)', 'color': '#c7d2fe', 'border': '1px solid rgba(99,102,241,0.4)'})
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Status", style={'color': '#cbd5e1', 'fontSize': '0.8rem'}),
                        html.H4("Pipelines", style={'color': '#ecf5ff', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Bundles · Components", style={'color': 'rgba(236,245,255,0.7)', 'fontSize': '0.9rem'})
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
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #22d3ee, #6366f1)'}),
                    html.Div([
                        html.Div([
                            html.Div("Pipeline Bundles", style={'fontWeight': '700', 'color': '#0b1b2d'}),
                            html.Div("Configurations with auto-created components", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                        ], className="flex-grow-1"),
                        html.Div([
                            dbc.Button(
                                [html.I(className="fas fa-plus me-2"), "Create New Pipeline"],
                                id="create-pipeline-button",
                                color="primary",
                                size="sm",
                                className="me-2"
                            ),
                            dbc.Button(
                                [html.I(className="fas fa-sync-alt me-2"), "Refresh"],
                                id="refresh-pipelines-button",
                                color="secondary",
                                size="sm",
                                outline=True
                            )
                        ], className="d-flex align-items-center")
                    ], className="d-flex align-items-start justify-content-between mb-3 gap-2"),
                    html.Div(id="pipeline-bundles-table-container")
                ], style={'padding': '1.25rem 1.5rem 1.5rem'})
            , width=12, style={
                'backgroundColor': '#ffffff',
                'borderRadius': '14px',
                'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                'border': '1px solid #e6ecf5',
                'marginBottom': '1.25rem'
            })
        ]),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="pipeline-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Pipeline ID"),
                            dbc.Input(
                                id="pipeline-id-input",
                                type="text",
                                placeholder="Enter pipeline ID (e.g., D, E, F)"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Pipeline Name"),
                            dbc.Input(
                                id="pipeline-name-input",
                                type="text",
                                placeholder="Enter pipeline name"
                            )
                        ], width=6)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Sector"),
                            dcc.Dropdown(
                                id="pipeline-sector-input",
                                options=[
                                    {'label': 'North Sector', 'value': 'sector-north'},
                                    {'label': 'South Sector', 'value': 'sector-south'}
                                ],
                                placeholder="Select sector",
                                clearable=False
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Location"),
                            dbc.Input(
                                id="pipeline-location-input",
                                type="text",
                                placeholder="Enter location (e.g., Building 1, Floor 2)"
                            )
                        ], width=6)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Description"),
                            dbc.Input(
                                id="pipeline-description-input",
                                type="text",
                                placeholder="Enter description"
                            )
                        ], width=12)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            html.H6("Sensor Limits", className="mb-2"),
                        ])
                    ], className="mb-2"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Temperature Min (°C)"),
                            dbc.Input(
                                id="temp-min-input",
                                type="number",
                                value=20.0,
                                step=0.1
                            )
                        ], width=3),
                        dbc.Col([
                            dbc.Label("Temperature Max (°C)"),
                            dbc.Input(
                                id="temp-max-input",
                                type="number",
                                value=50.0,
                                step=0.1
                            )
                        ], width=3),
                        dbc.Col([
                            dbc.Label("Pressure Min (PSI)"),
                            dbc.Input(
                                id="pressure-min-input",
                                type="number",
                                value=80.0,
                                step=0.1
                            )
                        ], width=3),
                        dbc.Col([
                            dbc.Label("Pressure Max (PSI)"),
                            dbc.Input(
                                id="pressure-max-input",
                                type="number",
                                value=120.0,
                                step=0.1
                            )
                        ], width=3)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H6("Auto-Created Components", className="text-muted mb-2"),
                                    html.Ul([
                                        html.Li("1 Temperature/Pressure Sensor (main bolt)"),
                                        html.Li("1 Main Control Valve"),
                                        html.Li("Default sensor limits and configurations")
                                    ])
                                ])
                            ], color="light", className="mb-3")
                        ])
                    ]),

                    dbc.Alert(id="pipeline-modal-alert", is_open=False, className="mb-3")
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button(
                    "Cancel",
                    id="pipeline-modal-cancel",
                    color="secondary",
                    className="me-2"
                ),
                dbc.Button(
                    "Create Pipeline",
                    id="pipeline-modal-save",
                    color="primary"
                )
            ])
        ], id="pipeline-modal", is_open=False, size="xl"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Confirm Delete")),
            dbc.ModalBody([
                html.P("Are you sure you want to delete this pipeline bundle?"),
                html.P("This will permanently remove:"),
                html.Ul([
                    html.Li("The pipeline configuration"),
                    html.Li("The associated sensor bolt"),
                    html.Li("The associated control valve"),
                    html.Li("All historical data and configurations")
                ]),
                html.P(id="delete-pipeline-name", className="fw-bold text-danger")
            ]),
            dbc.ModalFooter([
                dbc.Button(
                    "Cancel",
                    id="delete-modal-cancel",
                    color="secondary",
                    className="me-2"
                ),
                dbc.Button(
                    "Delete Pipeline Bundle",
                    id="delete-modal-confirm",
                    color="danger"
                )
            ])
        ], id="delete-pipeline-modal", is_open=False),

        dcc.Store(id='current-pipeline-id', data=None),
        dcc.Store(id='pipeline-modal-mode', data='create')

    ], fluid=True)


def create_pipeline_bundles_table(bundles):
    if not bundles:
        return dbc.Alert("No pipeline bundles found.", color="info")

    table_rows = []
    for pipeline_id, bundle in bundles.items():
        pipeline = bundle.get('pipeline', {})
        bundle_info = bundle.get('bundle_info', {})

        status = pipeline.get('status', 'unknown')
        status_color = 'success' if status == 'active' else 'secondary'

        is_complete = bundle_info.get('is_complete', False)
        completeness_color = 'success' if is_complete else 'warning'
        completeness_text = 'Complete' if is_complete else 'Incomplete'

        total_bolts = bundle_info.get('total_bolts', 0)
        total_valves = bundle_info.get('total_valves', 0)

        last_update_str = format_timestamp(pipeline.get('last_update'))

        table_rows.append(
            html.Tr([
                html.Td([
                    html.Strong(pipeline_id),
                    html.Br(),
                    html.Small(pipeline.get('name', ''), className="text-muted")
                ]),
                html.Td([
                    pipeline.get('location', 'N/A'),
                    html.Br(),
                    html.Small(pipeline.get('description', ''), className="text-muted")
                ]),
                html.Td([
                    dbc.Badge(
                        status.upper(),
                        color=status_color,
                        className="me-1"
                    ),
                    html.Br(),
                    dbc.Badge(
                        completeness_text,
                        color=completeness_color,
                        className="mt-1"
                    )
                ]),
                html.Td(f"{total_bolts} / {total_valves}"),
                html.Td(last_update_str),
                html.Td([
                    dbc.ButtonGroup([
                        dbc.Button(
                            "Edit",
                            id={"type": "edit-pipeline-btn", "index": pipeline_id},
                            color="outline-primary",
                            size="sm",
                            className="me-1"
                        ),
                        dbc.Button(
                            "Delete",
                            id={"type": "delete-pipeline-btn", "index": pipeline_id},
                            color="outline-danger",
                            size="sm",
                            disabled=False
                        )
                    ], size="sm")
                ])
            ])
        )

    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Pipeline"),
                html.Th("Location & Description"),
                html.Th("Status"),
                html.Th("Components (B/V)"),
                html.Th("Last Updated"),
                html.Th("Actions", style={"width": "150px"})
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, responsive=True)


def register_callbacks(app, service_client):

    @app.callback(
        Output('pipeline-bundles-store', 'data'),
        [Input('pipeline-bundles-interval', 'n_intervals'),
         Input('refresh-pipelines-button', 'n_clicks')],
        [State('auth-store', 'data')]
    )
    def load_pipeline_bundles(n_intervals, refresh_clicks, auth_data):
        if not auth_data or not auth_data.get('token'):
            return {}

        bundles = service_client.get_all_pipeline_bundles(auth_data['token'])
        return bundles

    @app.callback(
        Output('pipeline-bundles-table-container', 'children'),
        [Input('pipeline-bundles-store', 'data')]
    )
    def update_pipeline_bundles_table(bundles):
        return create_pipeline_bundles_table(bundles)

    @app.callback(
        [Output('pipeline-modal', 'is_open'),
         Output('pipeline-modal-title', 'children'),
         Output('pipeline-modal-mode', 'data'),
         Output('current-pipeline-id', 'data'),
         Output('pipeline-id-input', 'value'),
         Output('pipeline-name-input', 'value'),
         Output('pipeline-sector-input', 'value'),
         Output('pipeline-location-input', 'value'),
         Output('pipeline-description-input', 'value'),
         Output('temp-min-input', 'value'),
         Output('temp-max-input', 'value'),
         Output('pressure-min-input', 'value'),
         Output('pressure-max-input', 'value'),
         Output('pipeline-id-input', 'disabled'),
         Output('pipeline-modal-save', 'children')],
        [Input('create-pipeline-button', 'n_clicks'),
         Input({'type': 'edit-pipeline-btn', 'index': ALL}, 'n_clicks'),
         Input('pipeline-modal-cancel', 'n_clicks')],
        [State('pipeline-bundles-store', 'data')]
    )
    def handle_pipeline_modal(create_clicks, edit_clicks, cancel_clicks, bundles):
        if not ctx.triggered:
            raise PreventUpdate

        trigger = ctx.triggered[0]['prop_id']

        if 'pipeline-modal-cancel' in trigger:
            return False, "", "create", None, "", "", None, "", "", 20.0, 50.0, 80.0, 120.0, False, "Create Pipeline"

        if 'create-pipeline-button' in trigger and create_clicks:
            return True, "Create New Pipeline Bundle", "create", None, "", "", None, "", "", 20.0, 50.0, 80.0, 120.0, False, "Create Pipeline"

        if 'edit-pipeline-btn' in trigger and any(edit_clicks):
            pipeline_id = json.loads(trigger.split('.')[0])['index']
            bundle = bundles.get(pipeline_id, {})
            pipeline = bundle.get('pipeline', {})
            sensor_limits = pipeline.get('sensor_limits', {})

            return (
                True,
                f"Edit Pipeline Bundle: {pipeline_id}",
                "edit",
                pipeline_id,
                pipeline_id,
                pipeline.get('name', ''),
                pipeline.get('sector_id', None),
                pipeline.get('location', ''),
                pipeline.get('description', ''),
                sensor_limits.get('temp_min', 20.0),
                sensor_limits.get('temp_max', 50.0),
                sensor_limits.get('pressure_min', 80.0),
                sensor_limits.get('pressure_max', 120.0),
                True,
                "Save Changes"
            )

        raise PreventUpdate

    @app.callback(
        [Output('pipeline-modal', 'is_open', allow_duplicate=True),
         Output('pipeline-modal-alert', 'children'),
         Output('pipeline-modal-alert', 'is_open'),
         Output('pipeline-modal-alert', 'color'),
         Output('pipeline-bundles-interval', 'n_intervals', allow_duplicate=True)],
        [Input('pipeline-modal-save', 'n_clicks')],
        [State('pipeline-modal-mode', 'data'),
         State('current-pipeline-id', 'data'),
         State('pipeline-id-input', 'value'),
         State('pipeline-name-input', 'value'),
         State('pipeline-sector-input', 'value'),
         State('pipeline-location-input', 'value'),
         State('pipeline-description-input', 'value'),
         State('temp-min-input', 'value'),
         State('temp-max-input', 'value'),
         State('pressure-min-input', 'value'),
         State('pressure-max-input', 'value'),
         State('auth-store', 'data'),
         State('pipeline-bundles-interval', 'n_intervals')],
        prevent_initial_call=True
    )
    def save_pipeline_bundle(save_clicks, mode, current_id, pipeline_id, name, sector_id, location,
                           description, temp_min, temp_max, pressure_min, pressure_max,
                           auth_data, intervals):
        if not save_clicks or not auth_data or not auth_data.get('token'):
            raise PreventUpdate

        if not pipeline_id:
            return True, "Pipeline ID is required.", True, "danger", intervals

        if not sector_id:
            return True, "Sector is required.", True, "danger", intervals

        if mode == "create":
            bundle_data = {
                'pipeline_id': pipeline_id,
                'name': name or '',
                'sector_id': sector_id,
                'location': location or '',
                'description': description or '',
                'sensor_limits': {
                    'temp_min': temp_min or 20.0,
                    'temp_max': temp_max or 50.0,
                    'pressure_min': pressure_min or 80.0,
                    'pressure_max': pressure_max or 120.0
                }
            }

            result = service_client.create_pipeline_bundle(auth_data['token'], bundle_data)

            if 'error' in result:
                return True, f"Error creating pipeline bundle: {result['error']}", True, "danger", intervals

            return False, "", False, "success", intervals + 1

        else:
            updates = {
                'name': name or '',
                'sector_id': sector_id,
                'location': location or '',
                'description': description or '',
                'sensor_limits': {
                    'temp_min': temp_min or 20.0,
                    'temp_max': temp_max or 50.0,
                    'pressure_min': pressure_min or 80.0,
                    'pressure_max': pressure_max or 120.0
                }
            }

            result = service_client.update_pipeline_bundle(auth_data['token'], current_id, updates)

            if 'error' in result:
                return True, f"Error updating pipeline bundle: {result['error']}", True, "danger", intervals

            return False, "", False, "success", intervals + 1

    @app.callback(
        [Output('delete-pipeline-modal', 'is_open'),
         Output('delete-pipeline-name', 'children')],
        [Input({'type': 'delete-pipeline-btn', 'index': ALL}, 'n_clicks'),
         Input('delete-modal-cancel', 'n_clicks')],
        [State('pipeline-bundles-store', 'data'),
         State('current-pipeline-id', 'data')],
        prevent_initial_call=True
    )
    def handle_delete_modal(delete_clicks, cancel_clicks, bundles, current_pipeline_id):
        if not ctx.triggered:
            raise PreventUpdate

        trigger = ctx.triggered[0]['prop_id']

        if 'delete-modal-cancel' in trigger:
            return False, ""

        if 'delete-pipeline-btn' in trigger and any(delete_clicks):
            pipeline_id = json.loads(trigger.split('.')[0])['index']
            bundle = bundles.get(pipeline_id, {})
            pipeline = bundle.get('pipeline', {})

            pipeline_name = f"Pipeline {pipeline_id}"
            if pipeline.get('name'):
                pipeline_name += f" ({pipeline.get('name')})"

            return True, pipeline_name

        return False, ""

    @app.callback(
        Output('current-pipeline-id', 'data', allow_duplicate=True),
        [Input({'type': 'delete-pipeline-btn', 'index': ALL}, 'n_clicks')],
        prevent_initial_call=True
    )
    def set_current_pipeline_for_delete(delete_clicks):
        if not ctx.triggered or not any(delete_clicks):
            raise PreventUpdate

        trigger = ctx.triggered[0]['prop_id']
        pipeline_id = json.loads(trigger.split('.')[0])['index']
        return pipeline_id

    @app.callback(
        [Output('delete-pipeline-modal', 'is_open', allow_duplicate=True),
         Output('pipeline-bundles-interval', 'n_intervals', allow_duplicate=True)],
        [Input('delete-modal-confirm', 'n_clicks')],
        [State('current-pipeline-id', 'data'),
         State('auth-store', 'data'),
         State('pipeline-bundles-interval', 'n_intervals')],
        prevent_initial_call=True
    )
    def confirm_delete_pipeline_bundle(confirm_clicks, pipeline_id, auth_data, intervals):
        if not confirm_clicks or not pipeline_id or not auth_data or not auth_data.get('token'):
            raise PreventUpdate

        service_client.delete_pipeline_bundle(auth_data['token'], pipeline_id)
        return False, intervals + 1
