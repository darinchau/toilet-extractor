import requests
import datetime
import time
import json
from dataclasses import dataclass
import xml.etree.ElementTree as ET

URL = "https://www.fehd.gov.hk/english/map/getMapData.php?type=toilet&area=null&_={ts}"

@dataclass(frozen=True)
class GoogleMapLocationInfo:
    # Name,Latitude,Longitude,Description
    name: str
    latitude: float
    longitude: float
    description: str

def get_timestamp():
    now = datetime.datetime.now()
    timestamp = int(time.mktime(now.timetuple()) * 1000 + now.microsecond / 1000)
    return timestamp

def format_description(item):
    desc = []
    desc.append(item["nameTC"])
    desc.append(f"Address: {item['addressEN'].replace('&amp;', '&')}")
    desc.append(f"Opening Hours: {item['openHourEN']}")
    if item["contact1"]:
        desc.append(f"Contact: {item['contact1']}")
    if item["contact2"]:
        desc.append(f"Contact: {item['contact2']}")
    desc.append("")
    desc.append(f"Toilet ID: {item["mapID"]}")
    return "\n".join(desc)

def escape_xml_chars(text: str):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

def create_kml(locations):
    kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    document = ET.SubElement(kml, 'Document')

    for location in locations:
        placemark = ET.SubElement(document, 'Placemark')
        name = ET.SubElement(placemark, 'name')
        name.text = escape_xml_chars(location.name)

        description = ET.SubElement(placemark, 'description')
        description.text = escape_xml_chars(location.description)

        point = ET.SubElement(placemark, 'Point')
        coordinates = ET.SubElement(point, 'coordinates')
        coordinates.text = f'{location.longitude},{location.latitude}'

    # Generate the KML tree
    tree = ET.ElementTree(kml)
    return tree

def extract():
    response = requests.get(URL.format(ts=get_timestamp()))
    data = response.json()
    locations: list[GoogleMapLocationInfo] = []
    for item in data:
        latitude, longtitude = map(float, item["latitude"].split(","))
        locations.append(GoogleMapLocationInfo(
            name = item["nameEN"],
            latitude = latitude,
            longitude = longtitude,
            description=format_description(item)
        ))

    # Export to CSV
    kml_tree = create_kml(locations)
    kml_tree.write('toilet.kml', xml_declaration=True, encoding='utf-8', method='xml')

if __name__ == "__main__":
    extract()
