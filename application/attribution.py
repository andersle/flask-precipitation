"""Add an extra attribution to a folium map."""
from branca.element import Figure, MacroElement
from jinja2 import Template


class Attribution(MacroElement):
    """Add attribution to a Leaflet map."""

    _template = Template("""
        {% macro script(this,kwargs) %}
        {{this._parent.get_name()}}.attributionControl.addAttribution({{this.attribution}});
        {% endmacro %}
        """)

    def __init__(self, attribution):
        """Set up the attribution."""
        super().__init__()
        self._name = 'Attribution'
        self.attribution = attribution

    def render(self, **kwargs):
        """Render the attribution."""
        super().render(**kwargs)

        figure = self.get_root()
        assert isinstance(figure, Figure), ('You cannot render this Element '
                                            'if it is not in a Figure.')
