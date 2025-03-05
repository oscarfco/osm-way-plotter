import streamlit as st
import folium
import requests
import json
from streamlit_folium import folium_static

st.set_page_config(page_title="OSM Way Plotter", layout="wide")

st.title("OSM Way Plotter")

# Input text box for JSON
way_ids_input = st.text_area("Enter JSON for way IDs", value='{"1": [123456, 789012]}')

def plot_osm_ways(way_ids_by_distance):
    overpass_url = "https://overpass-api.de/api/interpreter"

    # Flatten way IDs
    all_way_ids = [way_id for way_list in way_ids_by_distance.values() for way_id in way_list]
    
    query = f"""
    [out:json];
    (
        {"".join([f"way({way_id});" for way_id in all_way_ids])}
    );
    (._;>;);
    out body;
    """
    
    # Fetch data from Overpass API with SSL verification disabled and timeout
    try:
        st.info("Fetching data from Overpass API... This may take a moment.")
        response = requests.get(
            overpass_url, 
            params={"data": query}, 
            verify=False,  # Disable SSL verification
            timeout=30  # Add timeout to prevent hanging
        )
        
        # Suppress only the specific InsecureRequestWarning
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        if response.status_code != 200:
            st.error(f"Error fetching data: HTTP status {response.status_code}")
            return None

        overpass_data = response.json()
        
        if not overpass_data.get("elements"):
            st.warning("No data returned from the API. The way IDs might not exist.")
            return None
            
    except requests.exceptions.Timeout:
        st.error("Request timed out. The Overpass API might be busy. Please try again later.")
        return None
    except requests.exceptions.SSLError as e:
        st.error(f"SSL Error: {str(e)}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request Error: {str(e)}")
        return None
    except json.JSONDecodeError:
        st.error("Could not parse the response from the Overpass API.")
        return None

    # Extract nodes
    nodes = {
        node["id"]: (node["lat"], node["lon"])
        for node in overpass_data.get("elements", [])
        if node["type"] == "node"
    }

    # Extract ways
    way_geometries = {
        element["id"]: [nodes[node_id] for node_id in element["nodes"] if node_id in nodes]
        for element in overpass_data.get("elements", []) if element["type"] == "way"
    }

    if not way_geometries:
        st.warning("No valid ways found.")
        return None

    # Center map on the first way
    first_way = list(way_geometries.values())[0]
    center_lat = sum(lat for lat, lon in first_way) / len(first_way)
    center_lon = sum(lon for lat, lon in first_way) / len(first_way)

    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=15)

    # Define colors for different distances
    distance_levels = sorted(way_ids_by_distance.keys())
    color_palette = ["blue", "red", "green", "orange", "purple"]
    
    distance_colors = {
        dist: color_palette[i % len(color_palette)]
        for i, dist in enumerate(distance_levels)
    }

    # Plot ways
    for distance, way_list in way_ids_by_distance.items():
        color = distance_colors.get(distance, "black")
        for way_id in way_list:
            if way_id in way_geometries:
                folium.PolyLine(
                    way_geometries[way_id], 
                    color=color, 
                    weight=3, 
                    tooltip=f"Way {way_id} (Distance {distance})"
                ).add_to(folium_map)

    return folium_map, center_lat, center_lon

# Button to process input and generate map
if st.button("Generate Map"):
    try:
        way_ids_by_distance = json.loads(way_ids_input)
        result = plot_osm_ways(way_ids_by_distance)
        if result:
            folium_map, center_lat, center_lon = result
            folium_static(folium_map)  # Display map in Streamlit
            
            # Display center coordinates and Google Maps link
            st.write(f"Center coordinates: {center_lat:.6f}, {center_lon:.6f}")
            google_maps_url = f"https://www.google.com/maps?q={center_lat},{center_lon}"
            st.markdown(f"[Open in Google Maps]({google_maps_url})")
    except Exception as e:
        st.error(f"Error: {str(e)}")
