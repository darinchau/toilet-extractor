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
    data = sorted(data, key=lambda x: x["nameEN"])
    with open("toilet.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
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
        return unescape_xml_chars("\n".join(desc))

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

def get_all_parks() -> list[GoogleMapLocationInfo]:
    def format_description(entry):
        desc = [
            f"Name: {entry['properties']['Chi. Name']}",
            f"Address: {entry['properties']['Chi. Address']}",
        ]
        if "Opening Hours" in entry['properties']:
            desc.append(f"Opening Hours: {entry['properties']['Opening Hours']}")
        return unescape_xml_chars("\n".join(desc))

    URL = "https://www.map.gov.hk/mapviewer/map.do?catabbr=PARKS&num=true&results=true&cluster=true&lg=tc"

    r = requests.get(URL)
    faciinfo = r.text.split("var faciinfo = ")[1]

    curlybracketcnt = 0
    for i in range(len(faciinfo)):
        if faciinfo[i] == "{":
            curlybracketcnt += 1
        elif faciinfo[i] == "}":
            curlybracketcnt -= 1
        if curlybracketcnt == 0:
            break

    faciinfo = faciinfo[:i+1]
    faciinfo = json.loads(faciinfo)

    infos = []

    for entry in faciinfo['features']:
        latitude = float(entry['geometry']['coordinates'][1])
        longitude = float(entry['geometry']['coordinates'][0])
        name = entry['properties']['Eng. Name']

        has_toilet = "Facility Details" in entry['properties'] and "toilet" in entry['properties']['Facility Details'].lower()

        description = format_description(entry)

        info = GoogleMapLocationInfo(
            name=name,
            latitude=latitude,
            longitude=longitude,
            description=description,
            verified=has_toilet
        )
        infos.append(info)
    return infos

def extract():
    unverified_locations: list[GoogleMapLocationInfo] = []

    fns = [get_all_public_toilet, get_all_parks, get_all_sports_ground_parks]
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
