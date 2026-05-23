from dash import html, dcc, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import json
from typing import Dict, List
from datetime import datetime
from components.terminal_banner import print_banner



def create_layout(service_client):
    refresh_seconds = max(int(30000 / 1000), 1)
    return dbc.Container([
        dcc.Store(id='users-store', data=[]),
        dcc.Interval(id='users-interval', interval=30000, n_intervals=0),

        html.Div([
            html.Div([
                html.Div([
                    html.Span("Access Control", style={'letterSpacing': '0.08em', 'color': '#b6d0ff', 'fontSize': '0.85rem', 'fontWeight': '600'}),
                    html.H2([
                        html.I(className="fas fa-users-cog me-3", style={'color': '#8be9fd'}),
                        "User Management"
                    ], className="mb-1", style={'fontWeight': '700', 'color': '#ecf5ff'}),
                    html.P(
                        "Manage roles, credentials, and pipeline permissions with audit-friendly controls.",
                        className="mb-2",
                        style={'color': 'rgba(236,245,255,0.82)'}
                    ),
                    html.Div([
                        dbc.Badge("Secure", color="info", className="me-2", pill=True),
                        dbc.Badge(f"Auto refresh · {refresh_seconds}s", pill=True,
                                  style={'backgroundColor': 'rgba(99,102,241,0.25)', 'color': '#c7d2fe', 'border': '1px solid rgba(99,102,241,0.4)'})
                    ])
                ], className="flex-grow-1"),
                html.Div([
                    html.Div([
                        html.Div("Status", style={'color': '#cbd5e1', 'fontSize': '0.8rem'}),
                        html.H4("Users", style={'color': '#ecf5ff', 'marginBottom': '0.35rem', 'fontWeight': '700'}),
                        html.Div("Create · Edit · Revoke", style={'color': 'rgba(236,245,255,0.7)', 'fontSize': '0.9rem'})
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
                            html.Div("Users", style={'fontWeight': '700', 'color': '#0b1b2d'}),
                            html.Div("Directory with roles and permissions", style={'color': '#6b7280', 'fontSize': '0.9rem'})
                        ], className="flex-grow-1"),
                        html.Div([
                            dbc.Button(
                                [html.I(className="fas fa-user-plus me-2"), "Add New User"],
                                id="add-user-button",
                                color="primary",
                                size="sm",
                                className="me-2"
                            ),
                            dbc.Button(
                                [html.I(className="fas fa-sync-alt me-2"), "Refresh"],
                                id="refresh-users-button",
                                color="secondary",
                                size="sm",
                                outline=True
                            )
                        ], className="d-flex align-items-center")
                    ], className="d-flex align-items-start justify-content-between mb-3 gap-2"),
                    html.Div(id="users-table-container")
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
            dbc.ModalHeader(dbc.ModalTitle(id="user-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Username"),
                            dbc.Input(
                                id="user-username-input",
                                type="text",
                                placeholder="Enter username"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Email"),
                            dbc.Input(
                                id="user-email-input",
                                type="email",
                                placeholder="Enter email"
                            )
                        ], width=6)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Password"),
                            dbc.Input(
                                id="user-password-input",
                                type="password",
                                placeholder="Enter password (min 6 characters)"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Role"),
                            dbc.Select(
                                id="user-role-select",
                                options=[
                                    {"label": "Viewer", "value": "viewer"},
                                    {"label": "Operator", "value": "operator"},
                                    {"label": "Admin", "value": "admin"}
                                ],
                                value="viewer"
                            )
                        ], width=6)
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Sector"),
                            dbc.Select(
                                id="user-sector-select",
                                options=[
                                    {"label": "No Sector", "value": ""},
                                    {"label": "North Sector", "value": "sector-north"},
                                    {"label": "South Sector", "value": "sector-south"}
                                ],
                                value=""
                            )
                        ], width=6)
                    ], className="mb-3"),

                    dbc.Alert(id="user-modal-alert", is_open=False, className="mb-3")
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button(
                    "Cancel",
                    id="user-modal-cancel",
                    color="secondary",
                    className="me-2"
                ),
                dbc.Button(
                    "Save User",
                    id="user-modal-save",
                    color="primary"
                )
            ])
        ], id="user-modal", is_open=False, size="lg"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Confirm Delete")),
            dbc.ModalBody([
                html.P("Are you sure you want to delete this user?"),
                html.P(id="delete-user-name", className="fw-bold text-danger")
            ]),
            dbc.ModalFooter([
                dbc.Button(
                    "Cancel",
                    id="delete-modal-cancel",
                    color="secondary",
                    className="me-2"
                ),
                dbc.Button(
                    "Delete User",
                    id="delete-modal-confirm",
                    color="danger"
                )
            ])
        ], id="delete-user-modal", is_open=False),

        dcc.Store(id='current-user-id', data=None),
        dcc.Store(id='modal-mode', data='create')

    ], fluid=True)


def create_users_table(users):
    if not users:
        return dbc.Alert("No users found.", color="info")

    table_rows = []
    for user in users:
        role_badge_color = {
            'admin': 'danger',
            'operator': 'warning',
            'viewer': 'info'
        }.get(user.get('role', 'viewer'), 'info')

        table_rows.append(
            html.Tr([
                html.Td(user.get('username', 'N/A')),
                html.Td(user.get('email', 'N/A')),
                html.Td([
                    dbc.Badge(
                        user.get('role', 'viewer').title(),
                        color=role_badge_color,
                        className="me-1"
                    )
                ]),
                html.Td(user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'),
                html.Td([
                    dbc.ButtonGroup([
                        dbc.Button(
                            "Edit",
                            id={"type": "edit-user-btn", "index": user.get('id')},
                            color="outline-primary",
                            size="sm",
                            className="me-1"
                        ),
                        dbc.Button(
                            "Delete",
                            id={"type": "delete-user-btn", "index": user.get('id')},
                            color="outline-danger",
                            size="sm",
                            disabled=user.get('username') == 'admin'
                        )
                    ], size="sm")
                ])
            ])
        )

    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Username"),
                html.Th("Email"),
                html.Th("Role"),
                html.Th("Created"),
                html.Th("Actions", style={"width": "200px"})
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, responsive=True)


def register_callbacks(app, service_client):

    @app.callback(
        Output('users-store', 'data'),
        [Input('users-interval', 'n_intervals'),
         Input('refresh-users-button', 'n_clicks')],
        [State('auth-store', 'data')]
    )
    def load_users(n_intervals, refresh_clicks, auth_data):
        if not auth_data or not auth_data.get('token'):
            return []

        return service_client.get_all_users(auth_data['token'])

    @app.callback(
        Output('users-table-container', 'children'),
        [Input('users-store', 'data')]
    )
    def update_users_table(users):
        return create_users_table(users)

    @app.callback(
        [Output('user-modal', 'is_open'),
         Output('user-modal-title', 'children'),
         Output('modal-mode', 'data'),
         Output('current-user-id', 'data'),
         Output('user-username-input', 'value'),
         Output('user-email-input', 'value'),
         Output('user-password-input', 'value'),
         Output('user-role-select', 'value'),
         Output('user-sector-select', 'value')],
        [Input('add-user-button', 'n_clicks'),
         Input({'type': 'edit-user-btn', 'index': ALL}, 'n_clicks'),
         Input('user-modal-cancel', 'n_clicks')],
        [State('users-store', 'data'),
         State('auth-store', 'data')],
        prevent_initial_call=True
    )
    def handle_user_modal(add_clicks, edit_clicks, cancel_clicks, users, auth_data):
        triggered_id = ctx.triggered_id

        if triggered_id == 'user-modal-cancel':
            return False, "", "create", None, "", "", "", "viewer", ""

        if triggered_id == 'add-user-button':
            if add_clicks and add_clicks > 0:
                return True, "Add New User", "create", None, "", "", "", "viewer", ""
            raise PreventUpdate

        if isinstance(triggered_id, dict) and triggered_id.get('type') == 'edit-user-btn':
            clicked_index = triggered_id.get('index')
            clicked_value = None
            for i, clicks in enumerate(edit_clicks or []):
                if clicks and clicks > 0:
                    clicked_value = clicks
                    break

            if not clicked_value:
                raise PreventUpdate

            user = next((u for u in users if u.get('id') == clicked_index), None)

            if user and auth_data:
                return (
                    True,
                    f"Edit User: {user.get('username', 'N/A')}",
                    "edit",
                    clicked_index,
                    user.get('username', ''),
                    user.get('email', ''),
                    "",
                    user.get('role', 'viewer'),
                    user.get('sector_id', '') or ""
                )

        raise PreventUpdate

    @app.callback(
        [Output('user-modal-alert', 'children'),
         Output('user-modal-alert', 'is_open'),
         Output('user-modal-alert', 'color'),
         Output('users-interval', 'n_intervals', allow_duplicate=True)],
        [Input('user-modal-save', 'n_clicks')],
        [State('modal-mode', 'data'),
         State('current-user-id', 'data'),
         State('user-username-input', 'value'),
         State('user-email-input', 'value'),
         State('user-password-input', 'value'),
         State('user-role-select', 'value'),
         State('user-sector-select', 'value'),
         State('auth-store', 'data'),
         State('users-interval', 'n_intervals')],
        prevent_initial_call=True
    )
    def save_user(save_clicks, mode, user_id, username, email, password, role, selected_sector, auth_data, intervals):
        if not save_clicks or not auth_data or not auth_data.get('token'):
            raise PreventUpdate

        if not username or not email:
            return "Username and email are required.", True, "danger", intervals

        if mode == "create":
            if not password or len(password) < 6:
                return "Password must be at least 6 characters long.", True, "danger", intervals

            user_data = {
                'username': username,
                'email': email,
                'password': password,
                'role': role,
                'sector_id': selected_sector or None
            }

            result = service_client.create_user(auth_data['token'], user_data)

            if 'error' in result:
                print_banner(
                    "USER CREATE FAILED",
                    [
                        f"username: {username}",
                        f"role:     {role}",
                        f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                        f"reason:   {result['error']}",
                    ],
                    kind="danger",
                )
                return f"Error creating user: {result['error']}", True, "danger", intervals

            print_banner(
                "USER CREATED",
                [
                    f"username: {user_data.get('username', '?')}",
                    f"email:    {user_data.get('email', '?')}",
                    f"role:     {user_data.get('role', '?')}",
                    f"sector:   {user_data.get('sector_id') or '(none)'}",
                    f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                ],
                kind="success",
            )
            return "User created successfully!", True, "success", intervals + 1

        else:
            updates = {
                'email': email,
                'role': role,
                'sector_id': selected_sector or None
            }
            if password and len(password) >= 6:
                updates['password'] = password
            elif password and len(password) < 6:
                return "Password must be at least 6 characters long.", True, "danger", intervals

            result = service_client.update_user(auth_data['token'], user_id, updates)

            if 'error' in result:
                print_banner(
                    "USER UPDATE FAILED",
                    [
                        f"id:       {user_id}",
                        f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                        f"reason:   {result['error']}",
                    ],
                    kind="danger",
                )
                return f"Error updating user: {result['error']}", True, "danger", intervals

            print_banner(
                "USER UPDATED",
                [
                    f"id:       {user_id}",
                    f"email:    {email}",
                    f"role:     {role}",
                    f"sector:   {selected_sector or '(none)'}",
                    f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                ],
                kind="event",
            )
            return "User updated successfully!", True, "success", intervals + 1

    @app.callback(
        [Output('delete-user-modal', 'is_open'),
         Output('delete-user-name', 'children'),
         Output('current-user-id', 'data', allow_duplicate=True)],
        [Input({'type': 'delete-user-btn', 'index': ALL}, 'n_clicks'),
         Input('delete-modal-cancel', 'n_clicks')],
        [State('users-store', 'data')],
        prevent_initial_call=True
    )
    def handle_delete_modal(delete_clicks, cancel_clicks, users):
        if not ctx.triggered:
            raise PreventUpdate

        trigger = ctx.triggered[0]['prop_id']

        if 'delete-modal-cancel' in trigger:
            return False, "", None

        if 'delete-user-btn' in trigger and any(delete_clicks):
            user_id = json.loads(trigger.split('.')[0])['index']
            user = next((u for u in users if u.get('id') == user_id), None)

            if user:
                return True, f"{user.get('username', 'N/A')} ({user.get('email', 'N/A')})", user_id

        raise PreventUpdate

    @app.callback(
        [Output('delete-user-modal', 'is_open', allow_duplicate=True),
         Output('users-interval', 'n_intervals', allow_duplicate=True)],
        [Input('delete-modal-confirm', 'n_clicks')],
        [State('current-user-id', 'data'),
         State('auth-store', 'data'),
         State('users-interval', 'n_intervals')],
        prevent_initial_call=True
    )
    def confirm_delete_user(confirm_clicks, user_id, auth_data, intervals):
        if not confirm_clicks or not user_id or not auth_data or not auth_data.get('token'):
            raise PreventUpdate

        result = service_client.delete_user(auth_data['token'], user_id)
        if 'error' not in (result or {}):
            print_banner(
                "USER DELETED",
                [
                    f"id:       {user_id}",
                    f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                ],
                kind="event",
            )
        else:
            print_banner(
                "USER DELETE FAILED",
                [
                    f"id:       {user_id}",
                    f"by:       {(auth_data.get('user') or {}).get('username', '?')}",
                    f"reason:   {(result or {}).get('error', 'unknown')}",
                ],
                kind="danger",
            )
        return False, intervals + 1
