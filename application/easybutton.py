"""Add a Easy-Button to a folium map."""
from branca.element import CssLink, Figure, MacroElement, JavascriptLink
from jinja2 import Template


JSURL = (
    'https://cdn.jsdelivr.net/npm/'
    'leaflet-easybutton@2/src/easy-button.js'
)


CSSURL = (
    'https://cdn.jsdelivr.net/npm/'
    'leaflet-easybutton@2/src/easy-button.css'
)


class EasyButton(MacroElement):
    """Add a EasyButton to a Leaflet map. This button will just open a url."""

    _template = Template("""
        {% macro script(this,kwargs) %}
        L.easyButton("{{this.icon}}", function(btn, map){
          window.open("{{this.url}}", "_self");
        }).addTo({{this._parent.get_name()}});
        {% endmacro %}
        """)

    def __init__(self, icon, url):
        """Set up the button."""
        super().__init__()
        self._name = 'EasyButton'
        self.icon = icon
        self.url = url

    def render(self, **kwargs):
        """Render the button."""
        super().render(**kwargs)

        figure = self.get_root()
        assert isinstance(figure, Figure), ('You cannot render this Element '
                                            'if it is not in a Figure.')
        figure.header.add_child(
            CssLink(CSSURL),  # noqa
            name='easybuttoncss'
        )

        figure.header.add_child(
            JavascriptLink(JSURL),  # noqa
            name='easyButton'
        )
