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

def get_all_country_parks() -> list[GoogleMapLocationInfo]:
    """This is done manually. If there is a way to automate this, please do. Plus I only did about half of them anyway.
    https://www.afcd.gov.hk/english/country/cou_vis/cou_vis_rec/cou_toi.html"""
    toilets = [
        GoogleMapLocationInfo(
            "Public Toilet (South Lantau Road-Nam Shan)",
            22.256559689379547, 113.98831270061358,
            "公廁 (嶼南路-南山)"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Nam Shan Campsite, South Lantau Road)",
            22.256644832474617, 113.98845763094559,
            "公廁 (南大嶼路 南山營地)"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Mui Wo Mountain Bike Practice Ground)",
            22.258705572552277, 113.99986613743245,
            "公廁(梅窩越野單車練習場)"
        ),
        GoogleMapLocationInfo(
            "Toilet (Lung Fu Shan Picnic Site No. 1, Pinewood Battery Heritage Trail)",
            22.27790305492522, 114.13644522464604,
            "廁所 (松林砲台歷史徑 龍虎山郊遊場地1號)"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Pokfulam Reservoir Road)",
            22.265614219678238, 114.13648967301764,
            "公廁(水塘道)"
        ),
        GoogleMapLocationInfo(
            "Aberdeen P.H.A.B. Barbecue Site Public Restroom",
            22.254275937955676, 114.15957477060864,
            "香港仔傷健樂園燒烤場地公廁"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Mount Parker Road Barbecue Site 1)",
            22.27837711577922, 114.20994335202718,
            '公廁 (柏架山道燒烤場地1號)'
        ),
        GoogleMapLocationInfo(
            "Quarry Pass Public Toilet",
            22.266911301844218, 114.21356007662182,
            "大風坳公廁"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Tam Barbecue Site No 2)",
            22.259287889987462, 114.20280639634092,
            "公廁 (大潭燒烤場地2號)"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Tam Reservoir Road)",
            22.240122563710496, 114.22128148377504,
            "公廁 (大潭水塘道)"
        ),
        GoogleMapLocationInfo(
            "Woodside Biodiversity Education Centre",
            22.281265604679746, 114.21148626583111,
            "林邊生物多樣性自然教育中心"
        ),
        GoogleMapLocationInfo(
            "Tai Hang Tun Public Toilet",
            22.291331126956848, 114.30082344072834,
            "大坑墩公廁"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Hang Tun Barbecue Site)",
            22.290420697394367, 114.29995921039311,
            '公廁 (大坑墩燒烤場地)'
        ),
        GoogleMapLocationInfo(
            "Tai Tong Sweet Gum Woods Public Toilet",
            22.399286911625246, 114.03473163710609,
            "大棠楓香林公廁"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Tong Barbecue Site 1)",
            22.409739739902783, 114.03282190757892,
            '公廁 (大棠燒烤場地1號)'
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Tong Barbecue Site 6)",
            22.407507076310573, 114.03539527474744,
            "大棠燒烤場地6號"
        ),
        GoogleMapLocationInfo(
            "Lung Yue Road Public Restroom",
            22.369713625373503, 114.05068541640514,
            "龍如路公廁"
        ),
        GoogleMapLocationInfo(
            "Chuen Lung Village Public Toilet",
            22.394708079919308, 114.10747735140626,
            "川龍村公廁"
        ),
        GoogleMapLocationInfo(
            "Hong Kong Wetland Park",
            22.4694949654417, 114.0048962267541,
            "香港濕地公園"
        ),
        GoogleMapLocationInfo(
            "Public Toilet (Tai Mo Shan Kiosk)",
            22.405050937516226, 114.10580254623656,
            "公廁 (大帽山茶水亭)"
        ),
        GoogleMapLocationInfo(
            "Lead Mine Pass Toilet",
            22.412081998319188, 114.15821538655268,
            "鉛礦坳公廁"
        ),
    ]

    for t in toilets:
        object.__setattr__(t, "verified", True)
    return toilets

def extract():
    unverified_locations: list[GoogleMapLocationInfo] = []

    fns = [get_all_public_toilet, get_all_parks, get_all_sports_ground_parks, get_all_country_parks]
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
