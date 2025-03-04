from assetloader import GeoJSONFeature

import json

path = "saveData/palmapdata.json"

# Reading data from a json file ()


# TODO: REPLACE LATER.
def read_data():
    try:
        with open(path, "r", encoding="utf8") as f:
            geojson_string = f.read()
            geojson_dict = json.loads(geojson_string)
            feature_from_dict = GeoJSONFeature.from_dict(geojson_dict)

            return feature_from_dict

    except FileNotFoundError:
        print("File not found. Creating a new file with default values.")
        default_data = {"type": "FeatureCollection", "features": []}
        write_data([])
        return GeoJSONFeature.from_dict(default_data)


# Writing data to a json file
def write_data(data):
    default_data = {
        "type": "FeatureCollection",
        "features": [d.to_dict() for d in data],
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(default_data, file, ensure_ascii=False, indent=4)
