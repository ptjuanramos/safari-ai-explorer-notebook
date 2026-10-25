```python
%pip install osmnx networkx geopandas shapely folium earthengine-api pandas numpy
```

    Requirement already satisfied: osmnx in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (2.1.0)
    Requirement already satisfied: networkx in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (3.6.1)
    Requirement already satisfied: geopandas in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (1.1.4)
    Requirement already satisfied: shapely in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (2.1.2)
    Requirement already satisfied: folium in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (0.20.0)
    Requirement already satisfied: earthengine-api in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (1.7.33)
    Requirement already satisfied: pandas in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (3.0.3)
    Requirement already satisfied: numpy in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (2.5.0)
    Requirement already satisfied: requests>=2.30 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from osmnx) (2.34.2)
    Requirement already satisfied: pyogrio>=0.7.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from geopandas) (0.13.0)
    Requirement already satisfied: packaging in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from geopandas) (26.2)
    Requirement already satisfied: pyproj>=3.5.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from geopandas) (3.7.2)
    Requirement already satisfied: branca>=0.6.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from folium) (0.8.2)
    Requirement already satisfied: jinja2>=2.9 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from folium) (3.1.6)
    Requirement already satisfied: xyzservices in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from folium) (2026.3.0)
    Requirement already satisfied: google-cloud-storage in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from earthengine-api) (3.12.0)
    Requirement already satisfied: google-api-python-client>=1.12.1 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from earthengine-api) (2.198.0)
    Requirement already satisfied: google-auth>=2.29.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from earthengine-api) (2.55.1)
    Requirement already satisfied: google-auth-httplib2>=0.2.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from earthengine-api) (0.4.0)
    Requirement already satisfied: httplib2<1dev,>=0.9.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from earthengine-api) (0.32.0)
    Requirement already satisfied: pyparsing<4,>=3.1 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from httplib2<1dev,>=0.9.2->earthengine-api) (3.3.2)
    Requirement already satisfied: python-dateutil>=2.8.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from pandas) (2.9.0.post0)
    Requirement already satisfied: tzdata in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from pandas) (2026.2)
    Requirement already satisfied: google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-api-python-client>=1.12.1->earthengine-api) (2.31.0)
    Requirement already satisfied: uritemplate<5,>=3.0.1 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-api-python-client>=1.12.1->earthengine-api) (4.2.0)
    Requirement already satisfied: googleapis-common-protos<2.0.0,>=1.63.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client>=1.12.1->earthengine-api) (1.75.0)
    Requirement already satisfied: protobuf<8.0.0,>=5.29.6 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client>=1.12.1->earthengine-api) (7.35.1)
    Requirement already satisfied: proto-plus<2.0.0,>=1.24.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-api-core!=2.0.*,!=2.1.*,!=2.2.*,!=2.3.0,<3.0.0,>=1.31.5->google-api-python-client>=1.12.1->earthengine-api) (1.28.0)
    Requirement already satisfied: pyasn1-modules>=0.2.1 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-auth>=2.29.0->earthengine-api) (0.4.2)
    Requirement already satisfied: cryptography>=38.0.3 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-auth>=2.29.0->earthengine-api) (49.0.0)
    Requirement already satisfied: charset_normalizer<4,>=2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from requests>=2.30->osmnx) (3.4.7)
    Requirement already satisfied: idna<4,>=2.5 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from requests>=2.30->osmnx) (3.18)
    Requirement already satisfied: urllib3<3,>=1.26 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from requests>=2.30->osmnx) (2.7.0)
    Requirement already satisfied: certifi>=2023.5.7 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from requests>=2.30->osmnx) (2026.6.17)
    Requirement already satisfied: cffi>=2.0.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from cryptography>=38.0.3->google-auth>=2.29.0->earthengine-api) (2.0.0)
    Requirement already satisfied: pycparser in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from cffi>=2.0.0->cryptography>=38.0.3->google-auth>=2.29.0->earthengine-api) (3.0)
    Requirement already satisfied: MarkupSafe>=2.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from jinja2>=2.9->folium) (3.0.3)
    Requirement already satisfied: pyasn1<0.7.0,>=0.6.1 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from pyasn1-modules>=0.2.1->google-auth>=2.29.0->earthengine-api) (0.6.3)
    Requirement already satisfied: six>=1.5 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from python-dateutil>=2.8.2->pandas) (1.17.0)
    Requirement already satisfied: google-cloud-core<3.0.0,>=2.4.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-cloud-storage->earthengine-api) (2.6.0)
    Requirement already satisfied: google-resumable-media<3.0.0,>=2.7.2 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-cloud-storage->earthengine-api) (2.10.0)
    Requirement already satisfied: google-crc32c<2.0.0,>=1.6.0 in c:\users\juan\source\safari-ai-explorer-notebook\.venv\lib\site-packages (from google-cloud-storage->earthengine-api) (1.8.0)
    Note: you may need to restart the kernel to use updated packages.
    

    
    [notice] A new release of pip is available: 25.1.1 -> 26.2.1
    [notice] To update, run: python.exe -m pip install --upgrade pip
    


```python
import ee

ee.Authenticate()
ee.Initialize(project='project-0cf410a3-f35f-4911-9c5')

PLACE_NAME = "Tarangire National Park, Tanzania"
```


<p>To authorize access needed by Earth Engine, open the following
        URL in a web browser and follow the instructions:</p>
        <p><a href=https://code.earthengine.google.com/client-auth?scopes=https%3A//www.googleapis.com/auth/earthengine%20https%3A//www.googleapis.com/auth/cloud-platform%20https%3A//www.googleapis.com/auth/drive%20https%3A//www.googleapis.com/auth/devstorage.full_control&request_id=p1G1OMVHCj2cwsJNgK8IjI3eE0gWp5A-zAd2xmva-as&tc=6mBFcFoO_kpgK0U70cwXTtHKw99aenST1YiP0rSsKEw&cc=EvKobnBWST1nbS4jQp94MTkzX1IQcZq9wtCfF-b2f9A>https://code.earthengine.google.com/client-auth?scopes=https%3A//www.googleapis.com/auth/earthengine%20https%3A//www.googleapis.com/auth/cloud-platform%20https%3A//www.googleapis.com/auth/drive%20https%3A//www.googleapis.com/auth/devstorage.full_control&request_id=p1G1OMVHCj2cwsJNgK8IjI3eE0gWp5A-zAd2xmva-as&tc=6mBFcFoO_kpgK0U70cwXTtHKw99aenST1YiP0rSsKEw&cc=EvKobnBWST1nbS4jQp94MTkzX1IQcZq9wtCfF-b2f9A</a></p>
        <p>The authorization workflow will generate a code, which you should paste in the box below.</p>



    
    Successfully saved authorization token.
    


```python
from datetime import date
from park_road_network import ParkRoadNetwork
from chirps_provider import CHIRPSProvider
from edge_risk_enricher import EdgeRiskEnricher

import folium

def create_risk_map(lookback_days: int, date: date):

    nodes, edges = ParkRoadNetwork(PLACE_NAME).load()
    rain_provider = CHIRPSProvider()

    pixel_grid = rain_provider.frame_grid(edges.total_bounds)

    rain_pixels, image_collection = rain_provider.get_decayed_precipitation(
        pixel_grid,
        date=date.strftime("%Y-%m-%d"),
        lookback_days=lookback_days
    )

    enricher = EdgeRiskEnricher()
    edges_enriched = enricher.enrich(edges, rain_pixels)

    center_lat, center_lon = nodes["y"].mean(), nodes["x"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10)

    SURFACE_RISK_COLORS = {
        (0.0, 0.25): "#2ecc71",
        (0.25, 0.5): "#f39c12",
        (0.5, 0.75): "#e74c3c",
        (0.75, 1.01): "#7b241c",
    }

    def get_risk_color(surface_risk: float) -> str:
        for (low, high), color in SURFACE_RISK_COLORS.items():
            if low <= surface_risk < high:
                return color
        return "#7b241c"

    for _, row in edges_enriched.iterrows():
        coords = [(lat, lon) for lon, lat in row["geometry"].coords]
        road_type = row["road_type"]
        rain_mm = row["rain_mm"]
        travel_time = row["travel_time_m"]

        surface_risk = row["surface_risk"]

        folium.PolyLine(
            locations=coords,
            color=get_risk_color(surface_risk),
            weight=3,
            opacity=0.8,
            popup=(
                f"highway: {road_type}<br>"
                f"travel_time: {travel_time}<br>"
                f"rain_mm(accumualte over x (start - end) days): {rain_mm:.1f}<br>"
                f"surface_risk: {surface_risk:.2f}<br>"
                f"surface_risk: {surface_risk:.2f}"
            ),
        ).add_to(m)

    return m
```


```python
import ipywidgets as widgets
from IPython.display import display, clear_output
from datetime import date, datetime

date_picker = widgets.DatePicker(
    description="Date:",
    value=date(2024, 4, 30),
)

lookback_days_input = widgets.IntText(
    value=0,
    description="Lookback days:",
    disabled=False,
)

load_button = widgets.Button(
    description="Load Map",
    button_style="primary",
)

output = widgets.Output()

```


```python
def on_render_clicked(_):
    date = date_picker.value
    lookback_days = lookback_days_input.value

    with output:
        clear_output(wait=True)

        m = create_risk_map(
            date=date,
            lookback_days=lookback_days,
        )
        display(m)


load_button.on_click(on_render_clicked)
```


```python
display(
    widgets.HBox([date_picker, lookback_days_input, load_button]),
    output,
)
```


    HBox(children=(DatePicker(value=datetime.date(2024, 4, 30), description='Date:', step=1), IntText(value=0, des…



    Output()

