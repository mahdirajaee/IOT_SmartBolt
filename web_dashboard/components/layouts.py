from dash import html, dcc
import dash_bootstrap_components as dbc
from datetime import datetime


def format_timestamp(timestamp):
    if timestamp == 'Unknown' or not timestamp:
        return 'Unknown'
    try:
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(timestamp)
    except Exception:
        return 'Unknown'


def create_login_layout():
    return html.Div([
        html.Div([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Img(src='/assets/polito_logo.png',
                                    style={
                                        'height': '120px',
                                        'marginBottom': '2rem',
                                        'filter': 'brightness(0) invert(1) drop-shadow(0 4px 6px rgba(0,0,0,0.1))'
                                    }),
                            html.H2("POLITECNICO DI TORINO",
                                   className="text-white mb-3",
                                   style={
                                       'fontWeight': '200',
                                       'letterSpacing': '4px',
                                       'fontSize': '1rem'
                                   }),
                            html.Div(style={
                                'width': '60px',
                                'height': '2px',
                                'backgroundColor': 'rgba(255,255,255,0.5)',
                                'margin': '0 auto 2rem auto'
                            }),
                        ], className="text-center mb-5")
                    ], width=12)
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-sign-in-alt",
                                          style={
                                              'fontSize': '3rem',
                                              'color': '#003576',
                                              'marginBottom': '1.5rem'
                                          })
                                ], className="text-center"),
                                html.H3("Sign In",
                                       className="text-center mb-2",
                                       style={'fontWeight': '600', 'color': '#2c3e50'}),
                                html.P("Access the IoT Pipeline Monitoring System",
                                      className="text-center text-muted mb-4",
                                      style={'fontSize': '0.9rem'}),

                                dbc.Form([
                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-user"),
                                                         style={'backgroundColor': '#f8f9fa', 'borderRight': 'none'}),
                                        dbc.Input(
                                            id="username-input",
                                            type="text",
                                            placeholder="Username",
                                            autofocus=True,
                                            style={'borderLeft': 'none', 'paddingLeft': '0'}
                                        )
                                    ], className="mb-3"),

                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-lock"),
                                                         style={'backgroundColor': '#f8f9fa', 'borderRight': 'none'}),
                                        dbc.Input(
                                            id="password-input",
                                            type="password",
                                            placeholder="Password",
                                            style={'borderLeft': 'none', 'paddingLeft': '0'}
                                        )
                                    ], className="mb-3"),

                                    dbc.Alert(
                                        id="login-error",
                                        is_open=False,
                                        color="danger",
                                        className="mb-3",
                                        style={'borderRadius': '10px'}
                                    ),

                                    dbc.Button([
                                        html.I(className="fas fa-arrow-right me-2"),
                                        "Sign In"
                                    ],
                                        id="login-button",
                                        color="primary",
                                        className="w-100 mb-3",
                                        size="lg",
                                        n_clicks=0,
                                        style={
                                            'background': 'linear-gradient(135deg, #003576 0%, #00509E 100%)',
                                            'border': 'none',
                                            'borderRadius': '10px',
                                            'fontWeight': '600',
                                            'padding': '0.8rem'
                                        }
                                    ),

                                    html.Div([
                                        dbc.Button([
                                            html.I(className="fas fa-home me-2"),
                                            "Back to Landing Page"
                                        ],
                                            href="/",
                                            color="link",
                                            className="text-decoration-none",
                                            style={'color': '#003576', 'fontWeight': '500'}
                                        )
                                    ], className="text-center")
                                ])
                            ], style={'padding': '2.5rem'})
                        ], style={
                            'borderRadius': '20px',
                            'boxShadow': '0 10px 40px rgba(0,0,0,0.15)',
                            'border': 'none',
                            'backgroundColor': '#ffffff'
                        })
                    ], width={"size": 10, "offset": 1}, md={"size": 8, "offset": 2}, lg={"size": 5, "offset": 0})
                ], justify="center")
            ], fluid=True, style={'maxWidth': '1200px'})
        ], style={
            'background': 'linear-gradient(135deg, #002147 0%, #003576 50%, #00509E 100%)',
            'minHeight': '100vh',
            'display': 'flex',
            'alignItems': 'center',
            'padding': '3rem 0'
        })
    ])


def create_navbar(user_info):
    username = user_info.get('username', 'User') if user_info else 'User'
    role = user_info.get('role', 'viewer') if user_info else 'viewer'

    nav_items = [
        dbc.NavItem(dbc.NavLink("Overview", href="/overview", id="nav-overview")),
        dbc.NavItem(dbc.NavLink("Pipelines", href="/pipelines", id="nav-pipelines")),
        dbc.NavItem(dbc.NavLink("Alerts", href="/alerts", id="nav-alerts")),
        dbc.NavItem(dbc.NavLink("Analytics", href="/analytics", id="nav-analytics")),
    ]

    if role in ['admin', 'operator']:
        nav_items.append(
            dbc.NavItem(dbc.NavLink("Control", href="/control", id="nav-control"))
        )


    if role == 'admin':
        nav_items.append(
            dbc.NavItem(dbc.NavLink("Users", href="/users", id="nav-users"))
        )
        nav_items.append(
            dbc.NavItem(dbc.NavLink("Pipeline Management", href="/pipeline-management", id="nav-pipeline-management"))
        )

    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.NavbarBrand("IoT Pipeline Monitor", className="ms-2")
                ], width="auto"),
            ], align="center", className="g-0"),

            dbc.Row([
                dbc.Col([
                    dbc.Nav(nav_items, className="me-auto", navbar=True)
                ])
            ], className="flex-grow-1"),

            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-user me-2"),
                        html.Span(f"{username} ({role})", className="text-light me-2"),
                        html.Span(" | ", className="text-light"),
                        dbc.Button(
                            "Logout",
                            id="logout-button",
                            color="link",
                            className="text-light p-0 ms-2",
                            style={"textDecoration": "none"}
                        )
                    ], className="navbar-text")
                ], width="auto")
            ], align="center", className="g-0")
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-3"
    )


