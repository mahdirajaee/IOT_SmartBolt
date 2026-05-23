#!/usr/bin/env python3

import dash_bootstrap_components as dbc
from dash import html


def create_layout():
    return html.Div(
        [
            create_hero(),
            create_features(),
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
