import dash
from dash import Dash, html, dcc, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import os
import sys
import secrets
from datetime import datetime
from dotenv import load_dotenv
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_utils import CatalogClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO if os.getenv('DEBUG', 'false').lower() != 'true' else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from components.auth import AuthManager
from components.service_client import ServiceClient
from components.layouts import create_navbar, create_login_layout

from pages import landing, overview, pipelines, alerts, analytics, control, users, pipeline_management

app = Dash(__name__,
          external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
          suppress_callback_exceptions=True,
          title="IoT Pipeline Monitor",
          update_title=None)

configured_key = os.getenv('SECRET_KEY')
if not configured_key:
    logger.warning("SECRET_KEY not set. Sessions will be invalidated on restart. Set SECRET_KEY env var for persistence.")
app.server.secret_key = configured_key or secrets.token_hex(32)

auth_manager = AuthManager()
service_client = ServiceClient()

@app.server.route('/health')
def health_check():
    import json as _json
    from flask import Response
    return Response(
        _json.dumps({"status": "healthy", "service": "web_dashboard"}),
        mimetype='application/json'
    )

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='auth-store', storage_type='session'),
    dcc.Store(id='refresh-trigger', data=0),
    html.Div(id='page-content')
])

def _access_denied(requirement):
    return dbc.Container([
        dbc.Alert(f"Access Denied: You need {requirement}.", color="danger", className="mt-4")
    ])

@app.callback(
    [Output('page-content', 'children'),
     Output('url', 'pathname')],
    [Input('url', 'pathname'),
     Input('auth-store', 'data')]
)
def display_page(pathname, auth_data):
    try:
        if pathname == '/' or pathname is None:
            return landing.create_layout(), '/'

        if not auth_data or not auth_data.get('token'):
            logger.debug(f"No auth data for path: {pathname}")
            if pathname != '/login':
                return create_login_layout(), '/login'
            return create_login_layout(), dash.no_update

        if not auth_manager.verify_token(auth_data.get('token')):
            logger.warning("Token verification failed, redirecting to login")
            return create_login_layout(), '/login'

        if pathname == '/login':
            pathname = '/overview'

        try:
            navbar = create_navbar(auth_data.get('user', {}))
        except Exception as navbar_error:
            logger.error(f"Error creating navbar: {navbar_error}")
            navbar = dbc.Navbar(
                dbc.Container([
                    dbc.NavbarBrand("IoT Dashboard", className="ms-2"),
                    dbc.Nav([
                        dbc.NavItem(dbc.NavLink("Overview", href="/overview")),
                        dbc.NavItem(dbc.NavLink("Pipelines", href="/pipelines")),
                        dbc.NavItem(dbc.NavLink("Alerts", href="/alerts")),
                        dbc.NavItem(dbc.NavLink("Analytics", href="/analytics")),
                    ], navbar=True, className="me-auto"),
                    html.Div([
                        html.Span(auth_data.get('user', {}).get('username', 'User'), className="text-light me-3"),
                        dbc.Button("Logout", id="logout-button", color="link", className="text-light")
                    ])
                ], fluid=True),
                color="dark",
                dark=True,
                className="mb-3"
            )

        if pathname == '/overview':
            page_content = overview.create_layout(service_client)
        elif pathname == '/pipelines':
            page_content = pipelines.create_layout(service_client)
        elif pathname == '/alerts':
            page_content = alerts.create_layout(service_client)
        elif pathname == '/analytics':
            page_content = analytics.create_layout(service_client)
        elif pathname == '/control':
            user_role = auth_data.get('user', {}).get('role')
            if user_role in ['admin', 'operator']:
                page_content = control.create_layout(service_client, auth_data.get('token'))
            else:
                page_content = _access_denied("operator or admin privileges to access valve controls")
        elif pathname == '/users':
            user_role = auth_data.get('user', {}).get('role')
            if user_role == 'admin':
                page_content = users.create_layout(service_client)
            else:
                page_content = _access_denied("admin privileges to access user management")
        elif pathname == '/pipeline-management':
            user_role = auth_data.get('user', {}).get('role')
            if user_role == 'admin':
                page_content = pipeline_management.create_layout(service_client)
            else:
                page_content = _access_denied("admin privileges to access pipeline management")
        else:

            page_content = dbc.Container([
                html.H1("404: Page not found", className="text-center mt-5"),
                html.P(f"The page '{pathname}' could not be found.", className="text-center"),
                dbc.Button("Go to Overview", href="/overview", color="primary", className="d-block mx-auto")
            ])

        layout = html.Div([
            navbar,
            page_content
        ])

        return layout, pathname

    except Exception as e:
        logger.error(f"Error in display_page: {str(e)}", exc_info=True)
        try:
            error_navbar = create_navbar(auth_data.get('user', {})) if auth_data else None
        except Exception:
            error_navbar = None
        error_content = dbc.Container([
            dbc.Alert([
                html.H4("Dashboard Error", className="alert-heading"),
                html.Hr(),
                html.P(f"An error occurred while loading the page: {str(e)}"),
                html.P("Please try refreshing the page or contact support if the issue persists.", className="mb-0")
            ], color="danger", className="mt-4"),
            dbc.Button("Return to Overview", href="/overview", color="primary", className="mt-3")
        ])
        error_layout = html.Div([error_navbar, error_content]) if error_navbar else error_content
        return error_layout, dash.no_update

@app.callback(
    [Output('auth-store', 'data'),
     Output('login-error', 'children'),
     Output('login-error', 'is_open')],
    [Input('login-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('password-input', 'value')],
    prevent_initial_call=True
)
def handle_login(n_clicks, username, password):
    if not n_clicks:
        raise PreventUpdate

    try:
        if not username or not password:
            return dash.no_update, "Please enter both username and password", True

        logger.info(f"Login attempt for user: {username}")

        result = auth_manager.login(username, password)

        if result['success']:
            auth_data = {
                'token': result['token'],
                'user': result['user'],
                'login_time': datetime.now().isoformat()
            }
            logger.info(f"User {username} logged in successfully")
            return auth_data, "", False
        else:
            error_msg = result.get('error', 'Login failed')
            logger.warning(f"Failed login attempt for user {username}: {error_msg}")

            if "Connection" in error_msg:
                error_msg = "Cannot connect to Account Manager service. Please ensure it's running on port 8084."
            elif "Invalid" in error_msg:
                error_msg = "Invalid username or password. Please try again."

            return dash.no_update, error_msg, True

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return dash.no_update, f"Login error: {str(e)}", True

@app.callback(
    Output('auth-store', 'data', allow_duplicate=True),
    Input('logout-button', 'n_clicks'),
    State('auth-store', 'data'),
    prevent_initial_call=True
)
def handle_logout(n_clicks, auth_data):
    if n_clicks and auth_data:
        username = auth_data.get('user', {}).get('username', 'Unknown')
        logger.info(f"User {username} logged out")
        return None
    raise PreventUpdate

overview.register_callbacks(app, service_client)
pipelines.register_callbacks(app, service_client)
alerts.register_callbacks(app, service_client)
analytics.register_callbacks(app, service_client)
control.register_callbacks(app, service_client)
users.register_callbacks(app, service_client)
pipeline_management.register_callbacks(app, service_client)

if __name__ == '__main__':
    port = int(os.getenv('DASH_PORT', 8090))
    host = os.getenv('DASH_HOST', '127.0.0.1')
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    logger.info(f"Starting IoT Dashboard on http://{host}:{port}")
    logger.info("Make sure Account Manager is running on port 8084")

    catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
    catalog_client = CatalogClient(catalog_url)
    catalog_client.register_service(
        name="web_dashboard",
        host=host,
        port=port,
        health_endpoint="/health",
        description="Visual monitoring interface"
    )

    app.run(debug=debug, host=host, port=port)
