import hashlib
import hmac
import json
from enum import Enum
from typing import List, Union, Optional, Tuple
import requests
from difflib import SequenceMatcher
import logging
import os

import folium
import osmnx as ox
from shapely.geometry import Polygon, MultiPolygon, mapping, Point
from shapely.ops import transform
import pyproj
from functools import partial
import math


class LLMModel(Enum):
    """Enumeración de los diferentes modelos de LLM disponibles."""
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"


class LLMVersion(Enum):
    """Enumeración de los diferentes modelos de LLM disponibles."""
    OPENAI_4_1 = "gpt-4.1"
    OPENAI_4_1_MINI = "gpt-4.1-mini"
    OPENAI_4_1_NANO = "gpt-4.1-nano"
    CLAUDE_3_SONNET_20240229 = "claude-3-sonnet-20240229"
    GEMINI_1_5_FLASH_EXP = "gemini-1.5-flash"


class GeocodingProvider(Enum):
    """Available geocoding providers"""
    NOMINATIM = "nominatim"
    GOOGLE = "google"
    HERE = "here"
    MAPBOX = "mapbox"


class LocationType(Enum):
    """Available geocoding providers"""
    CITY = "city"
    NEIGHBORHOOD = "neighborhood"
    STREET = "street"
    REGION = "region"


def get_area_by_giving_location(query: str, default_location='Madrid,España') -> Polygon:
    """
    Enhanced geocoding with multiple providers and fallbacks
    """

    # 1. Try direct Nominatim search
    try:
        geom = _get_nominatim_area(query)
        if geom:
            logging.info(f"Found location '{query}' directly in Nominatim Area")
            return geom
    except Exception as e:
        logging.warning(f"Direct Nominatim search failed for '{query}': {e}")
    try:
        lat, lon = _get_nominatim_point(query)
        geom = create_meter_radius_circle(lat, lon, 1000)
        logging.info(f"Found location '{query}' directly in Nominatim Point. Will return 1km radius circle.")
        return geom
    except Exception as e:
        logging.info(f"Din't found location '{query}'. Returning default location '{default_location}'")
        geom = _get_nominatim_area(default_location)
        return geom


def _get_nominatim_area(query: str) -> Optional[Polygon]:
    """Try direct Nominatim search"""
    gdf = ox.geocode_to_gdf(query)
    if gdf.empty:
        return None

    # If there are multiple geometries, choose the one with highest place_rank
    gdf = gdf.explode(index_parts=False)
    gdf['area'] = gdf.geometry.area
    gdf = gdf.sort_values(['place_rank', 'area'], ascending=False).reset_index(drop=True)
    geom = gdf.loc[0, 'geometry']

    return geom


def _get_nominatim_point(query: str) -> tuple[float, float]:
    """Try direct Nominatim search"""
    return ox.geocode(query)


def create_interactive_map(geom: Union[Polygon, MultiPolygon], output_html: str = "map.html"):
    if geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)
    else:
        raise ValueError("Geometría no soportada: {}".format(geom.geom_type))
    # Folium expects coords in [lat, lon] order
    coords_latlon = [(lat, lon) for lon, lat in coords]

    # Center map on the polygon centroid
    center_lat = sum(lat for lat, _ in coords_latlon) / len(coords_latlon)
    center_lon = sum(lon for _, lon in coords_latlon) / len(coords_latlon)

    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

    # Add polygon
    folium.Polygon(
        locations=coords_latlon,
        color="blue",
        weight=2,
        fill=True,
        fill_opacity=0.3
    ).add_to(m)

    # Save to HTML
    m.save(output_html)


def find_hmac_sha256(message, key):
    # print(f"Finding HMAC SHA256 for message: {message} and key: {key}")
    try:
        # Create HMAC SHA256 hash
        h = hmac.new(key.encode('utf-8'),
                     message.encode('utf-8'),
                     hashlib.sha256)

        # Get hex digest
        signature = h.hexdigest()
        return signature
    except Exception:
        return None


def to_idealista_multipolygon(geom: Union[Polygon, MultiPolygon]) -> str:
    """
    Convierte coordenadas de un polígono a formato Idealista
    """
    if geom.geom_type == 'Polygon':
        poly = MultiPolygon([geom])
    else:
        poly = geom
    geojson = mapping(poly)
    geojson["coordinates"] = [[[[x, y, 0] for x, y in ring] for ring in polygon]
                              for polygon in geojson["coordinates"]]
    # Dump to JSON string
    geojson_str = json.dumps(geojson)
    return geojson_str


def create_meter_radius_circle(lat: float, lng: float, metro: int) -> Polygon:
    # Create a point at the given coordinates
    point = Point(lng, lat)
    proj_string = "+proj=utm +zone=30 +ellps=GRS80 +units=m +no_defs"

    # Create the projection
    project = partial(
        pyproj.transform,
        pyproj.Proj('EPSG:4326'),  # source coordinate system (WGS84)
        pyproj.Proj(proj_string)  # target coordinate system (UTM)
    )

    # Transform the point to UTM
    point_utm = transform(project, point)
    circle_utm = point_utm.buffer(metro)  # radius in meters

    # Transform back to WGS84
    project_back = partial(
        pyproj.transform,
        pyproj.Proj(proj_string),  # source coordinate system (UTM)
        pyproj.Proj('EPSG:4326')  # target coordinate system (WGS84)
    )

    circle_wgs84 = transform(project_back, circle_utm)

    return circle_wgs84
