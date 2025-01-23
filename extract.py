import requests
import datetime
import time
import json
from dataclasses import dataclass
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class GoogleMapLocationInfo:
    # Name,Latitude,Longitude,Description
    name: str
    latitude: float
    longitude: float
    description: str
    verified: bool = False

def get_timestamp():
    now = datetime.datetime.now()
    timestamp = int(time.mktime(now.timetuple()) * 1000 + now.microsecond / 1000)
    return timestamp

def escape_xml_chars(text: str):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

def unescape_xml_chars(text: str):
    return (text.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&apos;", "'"))

def create_kml(locations: list[GoogleMapLocationInfo]) -> ET.ElementTree:
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

def get_all_public_toilet() -> list[GoogleMapLocationInfo]:
    URL = "https://www.fehd.gov.hk/english/map/getMapData.php?type=toilet&area=null&_={ts}"
    def format_description(item):
        desc = ["Public Toilet"]
        desc.append(item["nameTC"])
        desc.append(f"Address: {item['addressEN']}")
        desc.append(f"Opening Hours: {item['openHourEN']}")
        if item["contact1"]:
            desc.append(f"Contact: {item['contact1']}")
        if item["contact2"]:
            desc.append(f"Contact: {item['contact2']}")
        desc.append("")
        desc.append(f"Toilet ID: {item["mapID"]}")
        return unescape_xml_chars("\n".join(desc))

    response = requests.get(URL.format(ts=get_timestamp()))
    data = response.json()
    locations: list[GoogleMapLocationInfo] = []
    for item in data:
        latitude, longtitude = map(float, item["latitude"].split(","))
        locations.append(GoogleMapLocationInfo(
            name = item["nameEN"],
            latitude = latitude,
            longitude = longtitude,
            description=format_description(item),
            verified = True,
        ))
    return locations

def get_all_sports_ground_parks() -> list[GoogleMapLocationInfo]:
    URL = "https://www.smartplay.lcsd.gov.hk/website/tc/facility/fee.json"

    def format_description(item):
        desc = []
        desc.append(item["name"])
        desc.append(f"Address: {item['addr']}")
        for phone in item['phone']:
            desc.append(f"Phone: {phone}")
        desc.append("")
        desc.append(f"Source: {item["url"]}")
        return "\n".join(desc)

    r = requests.get(URL)
    data = r.json()
    mapinfos: list[GoogleMapLocationInfo] = []
    for entry in data:
        try:
            info = requests.get(entry['url'])
        except requests.exceptions.RequestException as e:
            print("Error getting", entry['url'])
            continue
        verified = True
        if info.status_code != 200:
            print("Error getting", entry['url'])
            verified = False
        elif "洗手間" not in info.text:
            print("No toilet in", entry['url'])
            verified = False
        mapinfo = GoogleMapLocationInfo(
            name=entry['name'],
            latitude=entry['lat'],
            longitude=entry['lng'],
            description=format_description(entry),
            verified=verified
        )
        mapinfos.append(mapinfo)
    return mapinfos

def extract():
    unverified_locations: list[GoogleMapLocationInfo] = []

    fns = [get_all_public_toilet, get_all_sports_ground_parks]
    for fn in fns:
        locations = fn()
        unverified_locations.extend([loc for loc in locations if not loc.verified])
        locations = [loc for loc in locations if loc.verified]
        kml_tree = create_kml(locations)
        name = fn.__name__.replace("get_all_", "")
        kml_tree.write(f'{name}.kml', xml_declaration=True, encoding='utf-8', method='xml')

    if unverified_locations:
        print(f"{len(unverified_locations)} unverified locations")
        kml_tree = create_kml(unverified_locations)
        kml_tree.write('unverified.kml', xml_declaration=True, encoding='utf-8', method='xml')

if __name__ == "__main__":
    extract()
