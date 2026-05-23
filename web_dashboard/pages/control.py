from dash import html, dcc, Input, Output, State
import dash
import dash_bootstrap_components as dbc
from datetime import datetime
import logging
import os
from components.layouts import format_timestamp
from components.terminal_banner import print_banner

logger = logging.getLogger(__name__)

def create_layout(service_client, auth_token):
    refresh_seconds = max(int(int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)) * 2 / 1000), 1)
    return dbc.Container([
        html.Div([
            html.Div([
                html.Div([
                    html.Span("Operations Deck", style={'letterSpacing': '0.08em', 'color': '#ffb7b2', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-cog me-3", style={'color': '#ffd166'}),
                        "Valve Control Panel"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#fff7ed'}),
                    html.P(
                        "Issue commands confidently with live context, safety cues, and full audit visibility.",
                        className="mb-2",
                        style={'color': 'rgba(255,247,237,0.82)'}
                    ),
                    html.Div([
                        dbc.Badge("Critical path", color="danger", className="me-2", pill=True),
                        dbc.Badge(f"Auto refresh · {refresh_seconds}s", color="warning", pill=True,
                                  style={'backgroundColor': 'rgba(255,255,255,0.14)', 'color': '#fff7ed'})
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Status", style={'color': '#ffe0d0', 'fontSize': '0.8rem'}),
                        html.H4("Control", style={'color': '#fff7ed', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Command + safety stack", style={'color': 'rgba(255,247,237,0.7)', 'fontSize': '0.9rem'})
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

        dbc.Alert([
            html.Div([
                html.Div(style={'width': '10px', 'height': '42px', 'borderRadius': '8px', 'background': 'linear-gradient(180deg, #be123c, #f97316)'}, className="me-3"),
                html.Div([
                    html.Div([
                        html.I(className="fas fa-exclamation-triangle me-2"),
                        html.Strong("Authorized Personnel Only")
                    ], style={'color': '#7c2d12', 'marginBottom': '0.25rem'}),
                    html.Div("Valve operations are logged and monitored. Verify authority before issuing commands.", style={'color': '#92400e'})
                ])
            ], className="d-flex align-items-start")
        ], color="warning", className="mb-4", style={'borderRadius': '14px', 'boxShadow': '0 12px 28px rgba(12,23,42,0.08)'}),

        dbc.Row([
            dbc.Col(
                html.Div([
                    html.Div([
                        html.Div([
                            html.Span("Select pipeline", style={'fontWeight': '700', 'color': '#0f172a', 'fontSize': '0.92rem'}),
                            html.P(
                                "Choose sector and pipeline to reveal valve commands.",
                                className="mb-0",
                                style={'color': '#6b7280', 'fontSize': '0.9rem'}
                            )
                        ], className="flex-grow-1"),
                        html.Div([
                            html.Div(
                                style={'width': '10px', 'height': '10px', 'borderRadius': '50%', 'backgroundColor': '#22c55e'},
                                className="me-2"
                            ),
                            html.Small("Live", style={'color': '#16a34a', 'fontWeight': '700'})
                        ], className="d-flex align-items-center")
                    ], className="d-flex align-items-start justify-content-between mb-3 gap-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Div([
                                    html.I(className="fas fa-map-marker-alt me-2", style={'color': '#be123c'}),
                                    html.Span("Sector", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="control-sector-filter",
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
                                    html.I(className="fas fa-project-diagram me-2", style={'color': '#be123c'}),
                                    html.Span("Pipeline", style={'fontWeight': '600', 'color': '#0f172a'})
                                ], className="mb-2"),
                                dcc.Dropdown(
                                    id="control-pipeline-selector",
                                    placeholder="Select a pipeline to control...",
                                    style={'backgroundColor': '#f8fafc'}
                                )
                            ])
                        ], md=8)
                    ], className="g-3"),
                    html.Div(id="control-pipeline-status", className="mt-3")
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
                html.Div([
                    html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #ef4444, #f97316)'}),
                    html.Div([
                        html.Div([
                            html.Div("Emergency Controls", style={'fontWeight': '700', 'color': '#0f172a'}),
                            html.Div("Global shutdown commands", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                        ], className="mb-3"),
                        dbc.Button(
                            [html.I(className="fas fa-exclamation-triangle me-2"), "Emergency Shutdown All"],
                            id="emergency-shutdown-btn",
                            color="danger",
                            size="lg",
                            className="w-100 mb-2"
                        ),
                        html.Small("Closes all valves in all pipelines", className="text-muted")
                    ], style={'padding': '1.25rem 1.5rem 1.5rem'})
                ], style={
                    'backgroundColor': '#ffffff',
                    'borderRadius': '14px',
                    'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
                    'border': '1px solid #e6ecf5',
                    'marginBottom': '1.25rem'
                }),
                md=4
            )
        ], className="mb-4 g-3"),

        html.Div([
            html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #0ea5e9, #22c55e)'}),
            html.Div([
                html.Div("Valve Controls", style={'fontWeight': '700', 'color': '#0f172a', 'marginBottom': '0.75rem'}),
                html.Div(id="valve-controls-grid"),
                html.Hr(),
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            "Open All Valves",
                            id="open-all-valves-btn",
                            color="success",
                            outline=True,
                            className="w-100"
                        )
                    ], md=6),
                    dbc.Col([
                        dbc.Button(
                            "Close All Valves",
                            id="close-all-valves-btn",
                            color="danger",
                            outline=True,
                            className="w-100"
                        )
                    ], md=6)
                ])
            ], style={'padding': '1.25rem 1.5rem 1.5rem'})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5',
            'marginBottom': '1.25rem'
        }),

        html.Div([
            html.Div(style={'height': '4px', 'borderRadius': '10px', 'background': 'linear-gradient(90deg, #0f172a, #334155)'}),
            html.Div([
                html.Div([
                    html.Div("Control History", style={'fontWeight': '700', 'color': '#0f172a'}),
                    html.Div("Logged operations with timestamps", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                ], className="d-flex align-items-start flex-column"),
                dbc.Button(
                    "Refresh",
                    id="control-history-refresh",
                    color="primary",
                    size="sm",
                    className="ms-auto"
                )
            ], className="d-flex align-items-center justify-content-between mb-3"),
            html.Div(id="control-history-list", style={"maxHeight": "400px", "overflowY": "auto"})
        ], style={
            'backgroundColor': '#ffffff',
            'borderRadius': '14px',
            'boxShadow': '0 12px 28px rgba(12,23,42,0.08)',
            'border': '1px solid #e6ecf5'
        }),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Confirm Action")),
            dbc.ModalBody(id="confirm-modal-body"),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="confirm-cancel", className="ms-auto", n_clicks=0),
                dbc.Button("Confirm", id="confirm-action", color="danger", n_clicks=0)
            ])
        ], id="confirm-modal", is_open=False),

        dcc.Store(id="pending-action"),

        dcc.Store(id="control-auth-token", data=auth_token),

        dbc.Alert(id="control-feedback", is_open=False, duration=4000, dismissable=True,
                  style={'position': 'fixed', 'top': '80px', 'right': '20px', 'zIndex': 9999, 'minWidth': '300px',
                         'boxShadow': '0 8px 24px rgba(0,0,0,0.15)', 'borderRadius': '12px'}),

        dcc.Interval(
            id='control-interval',
            interval=int(os.getenv('AUTO_REFRESH_INTERVAL', 5000)) * 2,
            n_intervals=0
        )
    ], fluid=True, style={'padding': '2rem 1.25rem', 'backgroundColor': '#f6f8fb'})

def register_callbacks(app, service_client):

    @app.callback(
        [Output('control-sector-filter', 'options'),
         Output('control-sector-filter', 'value')],
        [Input('auth-store', 'data')]
    )
    def update_control_sector_options(auth_data):
        if not auth_data:
            return [], None
        user = auth_data.get('user', {})
        user_id = user.get('id')
        role = user.get('role', 'viewer')
        options = service_client.get_sector_options_for_user(user_id, role)
        default_value = options[0]['value'] if options else None
        return options, default_value

    @app.callback(
        Output('control-pipeline-selector', 'options'),
        [Input('control-interval', 'n_intervals'),
         Input('control-sector-filter', 'value')]
    )
    def update_pipeline_options(n, sector_filter):
        pipelines = service_client.get_pipelines_by_sector(sector_filter)
        options = [
            {'label': f"Pipeline {p['pipeline_id']} - {p.get('name', 'Unnamed')} ({p.get('status', 'unknown')})",
             'value': p['pipeline_id']}
            for p in pipelines
        ]
        return options

    @app.callback(
        [Output('control-pipeline-status', 'children'),
         Output('valve-controls-grid', 'children')],
        [Input('control-pipeline-selector', 'value'),
         Input('control-interval', 'n_intervals')]
    )
    def update_pipeline_controls(pipeline_id, n):
        if not pipeline_id:
            return (
                html.P("Select a pipeline to view status", className="text-muted"),
                html.P("Select a pipeline to control valves", className="text-muted text-center")
            )

        pipeline = service_client.get_pipeline(pipeline_id)
        if not pipeline:
            return (
                html.P("Pipeline data not available", className="text-danger"),
                html.P("Unable to load valve controls", className="text-danger text-center")
            )

        status = pipeline.get('status', 'unknown')
        status_color = 'success' if status == 'active' else 'danger'

        status_display = dbc.Row([
            dbc.Col([
                html.Strong("Status: "),
                dbc.Badge(status.upper(), color=status_color, className="ms-2")
            ], md=4),
            dbc.Col([
                html.Strong("Location: "),
                html.Span(pipeline.get('location', {}).get('sector', 'Unknown'))
            ], md=4),
            dbc.Col([
                html.Strong("Last Update: "),
                html.Span(format_timestamp(pipeline.get('last_update', 'Unknown')))
            ], md=4)
        ])

        valves = pipeline.get('valves', [])
        if not valves:
            valve_controls = html.P("No valves available for this pipeline", className="text-muted text-center")
        else:
            valve_cards = []
            for valve in valves:
                valve_id = valve.get('valve_id', 'unknown')
                valve_status = valve.get('status', 'unknown')
                is_open = valve_status == 'open'

                card_color = 'success' if is_open else 'secondary'
                status_text = 'OPEN' if is_open else 'CLOSED'
                status_icon = html.I(className="fas fa-circle text-success") if is_open else html.I(className="fas fa-circle text-danger")

                valve_card = dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5(f"Valve {valve_id}", className="mb-2"),
                            html.Div([
                                status_icon,
                                dbc.Badge(status_text, color=card_color, className="ms-2")
                            ], className="mb-3"),
                            html.Small(f"Location: {valve.get('location', 'Unknown')}", className="d-block mb-3 text-muted"),
                            dbc.ButtonGroup([
                                dbc.Button(
                                    "Open",
                                    id={'type': 'valve-open-btn', 'valve_id': valve_id},
                                    color="success",
                                    size="sm",
                                    disabled=is_open,
                                    outline=not is_open
                                ),
                                dbc.Button(
                                    "Close",
                                    id={'type': 'valve-close-btn', 'valve_id': valve_id},
                                    color="danger",
                                    size="sm",
                                    disabled=not is_open,
                                    outline=is_open
                                )
                            ], className="w-100")
                        ])
                    ], color=card_color, outline=True)
                ], md=3, className="mb-3")

                valve_cards.append(valve_card)

            valve_controls = dbc.Row(valve_cards)

        return status_display, valve_controls

    @app.callback(
        [Output('confirm-modal', 'is_open'),
         Output('confirm-modal-body', 'children'),
         Output('pending-action', 'data')],
        [Input({'type': 'valve-open-btn', 'valve_id': dash.dependencies.ALL}, 'n_clicks'),
         Input({'type': 'valve-close-btn', 'valve_id': dash.dependencies.ALL}, 'n_clicks'),
         Input('open-all-valves-btn', 'n_clicks'),
         Input('close-all-valves-btn', 'n_clicks'),
         Input('emergency-shutdown-btn', 'n_clicks'),
         Input('confirm-cancel', 'n_clicks')],
        [State('control-pipeline-selector', 'value'),
         State('confirm-modal', 'is_open'),
         State('pending-action', 'data')],
        prevent_initial_call=True
    )
    def show_confirmation_modal(valve_open_clicks, valve_close_clicks,
                               open_all_clicks, close_all_clicks,
                               emergency_clicks, cancel_clicks,
                               pipeline_id, is_open, pending_action):
        ctx = dash.callback_context

        if not ctx.triggered:
            return False, "", None

        triggered_value = ctx.triggered[0]['value']
        if triggered_value is None or triggered_value == 0:
            return False, "", None

        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id == 'confirm-cancel':
            return False, "", None

        import json

        critical_warning = None
        if pipeline_id:
            alerts = service_client.get_alerts(pipeline_id=pipeline_id, limit=5)
            critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
            if critical_alerts and triggered_id != 'close-all-valves-btn':
                critical_warning = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    html.Strong("Warning: "),
                    f"Pipeline {pipeline_id} has {len(critical_alerts)} active critical alert(s). ",
                    "The Control Center may automatically override this action for safety."
                ], color="warning", className="mt-2 mb-0")

        if '{' in triggered_id:
            button_info = json.loads(triggered_id)
            valve_id = button_info['valve_id']
            action_type = 'open' if 'open' in button_info['type'] else 'close'

            base_message = f"Are you sure you want to {action_type} Valve {valve_id} in Pipeline {pipeline_id}?"
            message = html.Div([html.P(base_message), critical_warning]) if critical_warning and action_type == 'open' else base_message
            action_data = {
                'type': f'valve_{action_type}',
                'pipeline_id': pipeline_id,
                'valve_id': valve_id
            }
        elif triggered_id == 'open-all-valves-btn':
            base_message = f"Are you sure you want to OPEN ALL valves in Pipeline {pipeline_id}?"
            message = html.Div([html.P(base_message), critical_warning]) if critical_warning else base_message
            action_data = {
                'type': 'open_all',
                'pipeline_id': pipeline_id
            }
        elif triggered_id == 'close-all-valves-btn':
            message = f"Are you sure you want to CLOSE ALL valves in Pipeline {pipeline_id}?"
            action_data = {
                'type': 'close_all',
                'pipeline_id': pipeline_id
            }
        elif triggered_id == 'emergency-shutdown-btn':
            logger.warning("control: EMERGENCY SHUTDOWN modal opened (awaiting user confirmation)")
            print_banner(
                "EMERGENCY SHUTDOWN REQUESTED",
                [
                    "all valves will close across all pipelines if confirmed",
                    "awaiting user confirmation",
                ],
                kind="danger",
            )
            message = html.Div([
                html.H5("⚠️ EMERGENCY SHUTDOWN ⚠️", className="text-danger"),
                html.P("This will immediately close ALL valves in ALL pipelines!"),
                html.P("This action should only be used in emergency situations.", className="text-muted")
            ])
            action_data = {
                'type': 'emergency_shutdown'
            }
        else:
            return False, "", None

        return True, message, action_data

    @app.callback(
        [Output('control-history-list', 'children'),
         Output('control-feedback', 'children'),
         Output('control-feedback', 'color'),
         Output('control-feedback', 'is_open')],
        [Input('confirm-action', 'n_clicks'),
         Input('control-history-refresh', 'n_clicks'),
         Input('control-interval', 'n_intervals')],
        [State('pending-action', 'data'),
         State('control-auth-token', 'data')],
        prevent_initial_call=True
    )
    def execute_action_and_update_history(confirm_clicks, refresh_clicks, n_intervals,
                                          pending_action, auth_token):
        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        feedback_msg = ""
        feedback_color = "info"
        feedback_open = False

        if triggered_id == 'confirm-action' and pending_action:
            action_type = pending_action.get('type', '')
            pipeline_id = pending_action.get('pipeline_id') or '-'
            valve_id = pending_action.get('valve_id') or '-'
            logger.info(f"control: execute {action_type} pipeline={pipeline_id} valve={valve_id}")
            result = execute_valve_control(pending_action, auth_token, service_client)
            logger.info(f"control: result {action_type} pipeline={pipeline_id} valve={valve_id} success={bool(result)}")
            print_banner(
                f"VALVE COMMAND {'SUCCESS' if result else 'FAILED'}",
                [
                    f"action:   {action_type}",
                    f"pipeline: {pipeline_id}",
                    f"valve:    {valve_id}",
                ],
                kind="success" if result else "danger",
            )
            if result:
                feedback_msg = f"Command '{action_type.replace('_', ' ')}' executed successfully."
                feedback_color = "success"
            else:
                feedback_msg = f"Command '{action_type.replace('_', ' ')}' failed. Check logs for details."
                feedback_color = "danger"
            feedback_open = True

        history = service_client.get_control_history(auth_token) if auth_token else []

        if not history:
            return html.P("No control history available", className="text-muted"), feedback_msg, feedback_color, feedback_open

        history_items = []
        for entry in history[:20]:
            timestamp = entry.get('timestamp', 'Unknown')
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

            pipeline_id = entry.get('pipeline_id', 'Unknown')
            bolt_id = entry.get('bolt_id', '')
            action = entry.get('action', 'unknown')
            reason = entry.get('reason', '')
            rule = entry.get('rule', '')

            action_colors = {
                'no_action': 'secondary',
                'open_valve': 'success',
                'close_valve': 'warning',
                'emergency_shutdown': 'danger',
                'alert_operator': 'info'
            }
            badge_color = action_colors.get(action, 'secondary')

            target = f"{pipeline_id}/{bolt_id}" if bolt_id else pipeline_id

            history_card = dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Strong(f"{target}: "),
                            dbc.Badge(action.replace('_', ' ').title(), color=badge_color, className="me-2"),
                            html.Small(reason, className="text-muted") if reason else None
                        ], md=9),
                        dbc.Col([
                            html.Small(timestamp, className="text-muted")
                        ], md=3, className="text-end")
                    ])
                ], className="py-2")
            ], className="mb-2")

            history_items.append(history_card)

        return history_items, feedback_msg, feedback_color, feedback_open

def execute_valve_control(action_data, auth_token, service_client):
    action_type = action_data.get('type')

    try:
        if action_type in ('valve_open', 'valve_close'):
            command = 'open' if action_type == 'valve_open' else 'close'
            result = service_client.send_valve_command(
                action_data['pipeline_id'], action_data['valve_id'], command, auth_token
            )
            return result.get('success', False)

        elif action_type in ('open_all', 'close_all'):
            command = 'open' if action_type == 'open_all' else 'close'
            pipeline_id = action_data.get('pipeline_id')
            pipeline = service_client.get_pipeline(pipeline_id)
            if not pipeline:
                return False
            success = True
            for valve in pipeline.get('valves', []):
                vid = valve.get('valve_id') if isinstance(valve, dict) else valve
                result = service_client.send_valve_command(pipeline_id, vid, command, auth_token)
                if not result.get('success', False):
                    success = False
            return success

        elif action_type == 'emergency_shutdown':
            ok = service_client.activate_emergency(auth_token)
            if ok:
                print_banner(
                    "EMERGENCY SHUTDOWN ACTIVATED",
                    [
                        "system-wide valve closure dispatched",
                        f"target:   all valves across all sectors",
                    ],
                    kind="danger",
                )
            return ok

        return False

    except Exception as e:
        logger.error(f"Error executing valve control: {e}")
        return False
