from dash import Dash, html, dcc
import dash


class WebApp:
    appContainer: Dash = None
    appName: str = "Instrument control"

    @classmethod
    def initDashVariables(cls):
        cls.appContainer = Dash(__name__, use_pages=True)
        cls.appContainer.layout = html.Div(
            style={
                "fontFamily": "Arial, sans-serif",
                "margin": "0",
                "padding": "0",
                "backgroundColor": "#f4f4f4",
                "minHeight": "100vh",
            },
            children=[
                html.H1(
                    cls.appName,  # Title
                    style={
                        "textAlign": "center",
                        "color": "#333333",
                        "padding": "20px 0",
                        "marginBottom": "0",
                    },
                ),
                # NavBar
                html.Div(
                    [
                        html.Ul(
                            [
                                html.Li(
                                    dcc.Link(
                                        f"{page['name']}",
                                        href=page["relative_path"],
                                        style={
                                            "textDecoration": "none",
                                            "color": "white",
                                            "padding": "10px 20px",
                                            "display": "block",
                                        },
                                    ),
                                    style={
                                        "display": "inline-block",
                                        "marginRight": "10px",
                                    },
                                )
                                for page in dash.page_registry.values()
                            ],
                            style={
                                "listStyleType": "none",
                                "backgroundColor": "black",
                                "padding": "10px",
                                "textAlign": "center",
                                "margin": "0",
                            },
                        )
                    ]
                ),
                # Container for pages
                html.Div(
                    dash.page_container,
                    style={
                        "padding": "20px",
                        "backgroundColor": "white",
                        "margin": "20px auto",
                        "maxWidth": "80%",
                        "borderRadius": "10px",
                        "boxShadow": "0px 4px 8px rgba(0, 0, 0, 0.1)",
                    },
                ),
            ],
        )
