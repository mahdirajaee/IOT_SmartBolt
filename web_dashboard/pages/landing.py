#!/usr/bin/env python3

import dash_bootstrap_components as dbc
from dash import html


def create_layout():
    return html.Div(
        [
            create_hero(),
            create_features(),
            create_factory_floor(),
            create_role_previews(),
            create_footer(),
        ],
        className="landing-shell",
    )


def create_hero():
    return html.Section(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Img(
                                    src="/assets/polito_logo.png",
                                    style={"height": "86px", "marginRight": "1rem"},
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            "Politecnico di Torino",
                                            className="landing-kicker",
                                        ),
                                        html.Div(
                                            "Industrial IoT Pipeline Control",
                                            className="landing-subkicker",
                                        ),
                                    ]
                                ),
                            ],
                            className="landing-brand",
                        ),
                        html.H1(
                            "IoT Pipeline Monitoring System",
                            className="landing-title",
                        ),
                        html.P(
                            "Monitor pipeline temperature and pressure, detect anomalies, "
                            "and control valves across multiple sectors.",
                            className="landing-lede",
                        ),
                        html.Div(
                            [
                                dbc.Button(
                                    "Enter dashboard",
                                    href="/login",
                                    color="primary",
                                    className="landing-cta me-2",
                                ),
                            ],
                            className="landing-actions",
                        ),
                    ]
                )
            ],
            fluid=True,
            className="landing-container",
        ),
        className="landing-hero",
        id="top",
    )


def create_features():
    features = [
        ("Pipeline Monitoring",
         "Track temperature and pressure readings from sensors (bolts) "
         "installed on pipelines in the North and South sectors."),
        ("Anomaly Detection",
         "Automatically detect abnormal sensor readings and trigger "
         "alerts with severity levels from low to critical."),
        ("Valve Control",
         "Open or close valves manually or through automated rules "
         "that respond to detected anomalies."),
        ("Telegram Integration",
         "Receive alerts and send commands directly from Telegram "
         "for on-the-go monitoring."),
    ]

    return html.Section(
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    html.Div(f[0], className="step-title"),
                                    html.Div(f[1], className="step-copy"),
                                ],
                                className="step-card",
                            ),
                            md=3, sm=6,
                        )
                        for f in features
                    ],
                    className="g-4",
                ),
            ],
            fluid=True,
            className="section-shell",
        ),
        className="landing-section",
    )


# ── factory floor ──────────────────────────────────────

PIPELINES = [
    {"id": "N1", "sector": "north", "bolt": "bolt_n1", "valve": "valve_n1",
     "temp": 31.0, "psi": 100.0, "valve_st": "closed", "health": 92},
    {"id": "N2", "sector": "north", "bolt": "bolt_n2", "valve": "valve_n2",
     "temp": 30.3, "psi": 95.4, "valve_st": "closed", "health": 88},
    {"id": "N3", "sector": "north", "bolt": "bolt_n3", "valve": "valve_n3",
     "temp": 30.8, "psi": 95.7, "valve_st": "closed", "health": 90},
    {"id": "N4", "sector": "north", "bolt": "bolt_n4", "valve": "valve_n4",
     "temp": 28.5, "psi": 98.2, "valve_st": "closed", "health": 95},
    {"id": "S1", "sector": "south", "bolt": "bolt_s1", "valve": "valve_s1",
     "temp": 28.5, "psi": 95.4, "valve_st": "closed", "health": 91},
    {"id": "S2", "sector": "south", "bolt": "bolt_s2", "valve": "valve_s2",
     "temp": 32.4, "psi": 93.0, "valve_st": "closed", "health": 85},
    {"id": "S3", "sector": "south", "bolt": "bolt_s3", "valve": "valve_s3",
     "temp": 29.7, "psi": 96.6, "valve_st": "closed", "health": 89},
]


def _val_color(v, lo, hi):
    if v > hi:
        return "#ff6b6b"
    if v > (lo + hi) / 2:
        return "#ffa502"
    return "#7bf1a8"


def _health_bar(score):
    color = "#7bf1a8" if score >= 80 else ("#ffa502" if score >= 50 else "#ff6b6b")
    return html.Div(
        [
            html.Div(
                style={
                    "width": f"{score}%",
                    "height": "100%",
                    "background": color,
                    "borderRadius": "3px",
                    "transition": "width 0.6s ease",
                },
            ),
        ],
        style={
            "width": "100%",
            "height": "4px",
            "background": "rgba(255,255,255,0.08)",
            "borderRadius": "3px",
            "marginTop": "0.5rem",
        },
    )


def _pipeline_row(p):
    sec_color = "#4dd2ff" if p["sector"] == "north" else "#7bf1a8"
    v_color = "#7bf1a8" if p["valve_st"] == "open" else "#ff6b6b"
    t_color = _val_color(p["temp"], 20, 40)
    pr_color = _val_color(p["psi"], 80, 110)

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        p["id"],
                        className="ff-pid",
                    ),
                    html.Div(
                        p["sector"][0].upper(),
                        className="ff-sector-badge",
                        style={"background": f"{sec_color}20", "color": sec_color},
                    ),
                ],
                className="ff-label-col",
            ),

            html.Div(className="ff-pipe-seg"),

            html.Div(
                [
                    html.Div(className="ff-bolt-icon"),
                    html.Div(
                        [
                            html.Div(p["bolt"], className="ff-device-id"),
                            html.Div(
                                [
                                    html.Span(f"{p['temp']:.1f}°C",
                                              style={"color": t_color}),
                                    html.Span(" | "),
                                    html.Span(f"{p['psi']:.0f} PSI",
                                              style={"color": pr_color}),
                                ],
                                className="ff-readings",
                            ),
                        ],
                    ),
                ],
                className="ff-bolt-node",
            ),

            html.Div(className="ff-pipe-seg"),

            html.Div(
                [
                    html.Div(
                        className="ff-valve-icon",
                        style={"borderColor": v_color},
                    ),
                    html.Div(
                        [
                            html.Div(p["valve"], className="ff-device-id"),
                            html.Div(
                                p["valve_st"].upper(),
                                className="ff-valve-state",
                                style={"color": v_color},
                            ),
                        ],
                    ),
                ],
                className="ff-valve-node",
            ),

            html.Div(className="ff-pipe-seg"),

            html.Div(
                [
                    html.Div(
                        f"{p['health']}%",
                        className="ff-health-val",
                        style={
                            "color": "#7bf1a8" if p["health"] >= 80
                            else ("#ffa502" if p["health"] >= 50 else "#ff6b6b")
                        },
                    ),
                    _health_bar(p["health"]),
                ],
                className="ff-health-col",
            ),
        ],
        className="ff-row",
    )


def create_factory_floor():
    header = html.Div(
        [
            html.Div("PIPELINE", className="ff-hdr ff-label-col"),
            html.Div("", style={"width": "20px"}),
            html.Div("BOLT SENSOR", className="ff-hdr ff-bolt-node"),
            html.Div("", style={"width": "20px"}),
            html.Div("VALVE", className="ff-hdr ff-valve-node"),
            html.Div("", style={"width": "20px"}),
            html.Div("HEALTH", className="ff-hdr ff-health-col"),
        ],
        className="ff-header-row",
    )

    stats_north = [p for p in PIPELINES if p["sector"] == "north"]
    stats_south = [p for p in PIPELINES if p["sector"] == "south"]
    avg_temp = sum(p["temp"] for p in PIPELINES) / len(PIPELINES)
    avg_psi = sum(p["psi"] for p in PIPELINES) / len(PIPELINES)
    avg_health = sum(p["health"] for p in PIPELINES) / len(PIPELINES)

    summary_bar = html.Div(
        [
            html.Div(
                [
                    html.Div("7", className="ff-stat-val"),
                    html.Div("Pipelines", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div(f"{len(stats_north)}N / {len(stats_south)}S",
                             className="ff-stat-val"),
                    html.Div("Sectors", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div("7", className="ff-stat-val"),
                    html.Div("Bolts", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div("7", className="ff-stat-val"),
                    html.Div("Valves", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div(f"{avg_temp:.1f}°C", className="ff-stat-val"),
                    html.Div("Avg Temp", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div(f"{avg_psi:.0f} PSI", className="ff-stat-val"),
                    html.Div("Avg Pressure", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
            html.Div(
                [
                    html.Div(
                        f"{avg_health:.0f}%",
                        className="ff-stat-val",
                        style={
                            "color": "#7bf1a8" if avg_health >= 80
                            else "#ffa502"
                        },
                    ),
                    html.Div("Avg Health", className="ff-stat-label"),
                ],
                className="ff-stat-item",
            ),
        ],
        className="ff-summary-bar",
    )

    return html.Section(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div("Factory Floor", className="section-kicker"),
                        html.H2("Pipeline & Bolt Overview", className="section-title"),
                        html.P(
                            "All pipelines, sensors and valves across both sectors "
                            "in a single view.",
                            className="section-lede",
                        ),
                    ],
                    style={"marginBottom": "1.5rem"},
                ),
                summary_bar,
                html.Div(
                    [
                        header,
                        *[_pipeline_row(p) for p in PIPELINES],
                    ],
                    className="ff-table",
                ),
            ],
            fluid=True,
            className="section-shell",
        ),
        className="landing-section alt",
    )


# ── role previews ──────────────────────────────────────

def _role_preview(role, color, icon, tagline, pages, actions):
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        icon,
                        className="rp-icon",
                        style={"background": f"{color}18", "color": color},
                    ),
                    html.Div(
                        [
                            html.Div(role.upper(), className="rp-role",
                                     style={"color": color}),
                            html.Div(tagline, className="rp-tagline"),
                        ],
                    ),
                ],
                className="rp-header",
            ),

            html.Div("Dashboard Pages", className="rp-section-label"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                className="rp-page-dot",
                                style={"background": color},
                            ),
                            html.Span(page),
                        ],
                        className="rp-page-item",
                    )
                    for page in pages
                ],
                className="rp-page-list",
            ),

            html.Div("Actions", className="rp-section-label"),
            html.Div(
                [
                    html.Div(action, className="rp-action-chip",
                             style={"borderColor": f"{color}30"})
                    for action in actions
                ],
                className="rp-action-list",
            ),

            html.Div(
                [
                    html.Div(
                        className="rp-preview-bar",
                        style={"background": color},
                    ),
                    html.Div(
                        _mock_dashboard(role, color),
                        className="rp-preview-body",
                    ),
                ],
                className="rp-preview-window",
            ),
        ],
        className="rp-card",
    )


def _mock_dashboard(role, color):
    if role == "Admin":
        return html.Div(
            [
                html.Div(
                    [
                        _mock_stat("Users", "12", color),
                        _mock_stat("Services", "10/10", "#7bf1a8"),
                        _mock_stat("Pipelines", "7", "#4dd2ff"),
                        _mock_stat("Alerts", "3", "#ff6b6b"),
                    ],
                    className="rp-mock-stats",
                ),
                html.Div(
                    [
                        _mock_table_row("admin", "admin", "All Sectors"),
                        _mock_table_row("op_north", "operator", "Sector North"),
                        _mock_table_row("viewer1", "viewer", "Sector South"),
                    ],
                    className="rp-mock-table",
                ),
                html.Div(
                    [
                        html.Div("Pipeline Management", className="rp-mock-panel-title"),
                        html.Div(
                            [
                                html.Span("+ Create Pipeline",
                                          className="rp-mock-btn",
                                          style={"background": f"{color}20",
                                                 "color": color}),
                                html.Span("Edit Thresholds",
                                          className="rp-mock-btn",
                                          style={"background": "rgba(255,255,255,0.06)"}),
                            ],
                            className="rp-mock-btn-row",
                        ),
                    ],
                    className="rp-mock-panel",
                ),
            ],
        )
    elif role == "Operator":
        return html.Div(
            [
                html.Div(
                    [
                        _mock_stat("Active", "7/7", "#7bf1a8"),
                        _mock_stat("Temp", "30.2°C", "#ffa502"),
                        _mock_stat("Alerts", "2", "#ff6b6b"),
                    ],
                    className="rp-mock-stats",
                ),
                html.Div(
                    [
                        html.Div("Valve Control Panel", className="rp-mock-panel-title"),
                        html.Div(
                            [
                                _mock_valve("valve_n1", "CLOSED", "#ff6b6b"),
                                _mock_valve("valve_n2", "CLOSED", "#ff6b6b"),
                                _mock_valve("valve_s1", "OPEN", "#7bf1a8"),
                            ],
                            className="rp-mock-valves",
                        ),
                    ],
                    className="rp-mock-panel",
                ),
                html.Div(
                    [
                        html.Span("EMERGENCY SHUTDOWN",
                                  className="rp-mock-emergency"),
                    ],
                    className="rp-mock-panel",
                    style={"textAlign": "center"},
                ),
            ],
        )
    else:
        return html.Div(
            [
                html.Div(
                    [
                        _mock_stat("Health", "90%", "#7bf1a8"),
                        _mock_stat("Temp", "30.2°C", "#4dd2ff"),
                        _mock_stat("PSI", "96.3", "#4dd2ff"),
                    ],
                    className="rp-mock-stats",
                ),
                html.Div(
                    [
                        html.Div("Temperature Trend", className="rp-mock-panel-title"),
                        html.Div(className="rp-mock-chart"),
                    ],
                    className="rp-mock-panel",
                ),
                html.Div(
                    [
                        html.Div("Recent Alerts", className="rp-mock-panel-title"),
                        _mock_alert("N1", "High temp spike", "warning"),
                        _mock_alert("S2", "Pressure drop", "critical"),
                    ],
                    className="rp-mock-panel",
                ),
            ],
        )


def _mock_stat(label, value, color):
    return html.Div(
        [
            html.Div(value, style={"fontWeight": "700", "fontSize": "0.85rem",
                                   "color": color}),
            html.Div(label, style={"fontSize": "0.6rem", "color": "#9fb3d6"}),
        ],
        className="rp-mock-stat",
    )


def _mock_table_row(user, role, sector):
    role_colors = {"admin": "#c084fc", "operator": "#4dd2ff", "viewer": "#9fb3d6"}
    return html.Div(
        [
            html.Span(user, style={"flex": "1", "fontSize": "0.65rem",
                                   "color": "#c5d0e5"}),
            html.Span(role, style={"fontSize": "0.6rem", "fontWeight": "600",
                                   "color": role_colors.get(role, "#9fb3d6")}),
            html.Span(sector, style={"fontSize": "0.6rem", "color": "#9fb3d6",
                                     "marginLeft": "0.5rem"}),
        ],
        className="rp-mock-trow",
    )


def _mock_valve(vid, state, color):
    return html.Div(
        [
            html.Div(vid, style={"fontSize": "0.6rem", "color": "#c5d0e5"}),
            html.Div(state, style={"fontSize": "0.6rem", "fontWeight": "700",
                                   "color": color}),
        ],
        className="rp-mock-valve-item",
    )


def _mock_alert(pid, msg, severity):
    sev_colors = {"warning": "#ffa502", "critical": "#ff6b6b", "info": "#4dd2ff"}
    c = sev_colors.get(severity, "#9fb3d6")
    return html.Div(
        [
            html.Div(
                className="rp-mock-alert-dot",
                style={"background": c},
            ),
            html.Span(pid, style={"fontWeight": "600", "fontSize": "0.6rem",
                                  "color": "#f6f9ff", "marginRight": "0.3rem"}),
            html.Span(msg, style={"fontSize": "0.6rem", "color": "#9fb3d6"}),
        ],
        className="rp-mock-alert-row",
    )


def create_role_previews():
    return html.Section(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Div("Access Control", className="section-kicker"),
                        html.H2("Role-Based Dashboards", className="section-title"),
                        html.P(
                            "Three roles with different access levels. Each role sees "
                            "a tailored dashboard experience.",
                            className="section-lede",
                        ),
                    ],
                    style={"marginBottom": "2rem"},
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            _role_preview(
                                "Admin", "#c084fc", "A",
                                "Full system control & user management",
                                ["Overview", "Pipelines", "Alerts", "Analytics",
                                 "Control", "Users", "Pipeline Management"],
                                ["Create/delete users", "Assign pipelines",
                                 "Manage thresholds", "Create pipeline bundles",
                                 "Emergency shutdown", "View all sectors"],
                            ),
                            lg=4, md=12, className="mb-4",
                        ),
                        dbc.Col(
                            _role_preview(
                                "Operator", "#4dd2ff", "O",
                                "Monitor & control assigned sectors",
                                ["Overview", "Pipelines", "Alerts", "Analytics",
                                 "Control"],
                                ["Open/close valves", "Emergency shutdown",
                                 "View assigned sectors", "Acknowledge alerts",
                                 "Trigger decisions"],
                            ),
                            lg=4, md=12, className="mb-4",
                        ),
                        dbc.Col(
                            _role_preview(
                                "Viewer", "#7bf1a8", "V",
                                "Read-only monitoring & analytics",
                                ["Overview", "Pipelines", "Alerts", "Analytics"],
                                ["View pipeline status", "View temperature charts",
                                 "View pressure charts", "View alerts history",
                                 "View anomaly reports"],
                            ),
                            lg=4, md=12, className="mb-4",
                        ),
                    ],
                    className="g-4",
                ),
            ],
            fluid=True,
            className="section-shell",
        ),
        className="landing-section",
    )


def create_footer():
    return html.Footer(
        dbc.Container(
            [
                html.Div("IoT Pipeline Monitoring System", className="footer-title"),
                html.Div("Politecnico di Torino — 2025", className="footer-meta"),
            ],
            fluid=True,
            className="footer-shell",
        ),
        className="landing-footer",
        id="footer",
    )
