import json


class GeoJSONFeature:
    """GeoJSON class wrapper"""

    def __init__(self, geometry, properties=None, idv=None):
        """
        Initialize a GeoJSON Feature object.

        :param geometry: The geometry of the feature (e.g., Point, LineString, Polygon).
        :param properties: Optional properties of the feature (e.g., name, population).
        :param id: Optional identifier for the feature.
        """
        self.type = "Feature"
        self.geometry = geometry
        self.properties = properties or {}
        self.id = idv

    def to_dict(self):
        """
        Convert the GeoJSON Feature object to a dictionary.

        :return: Dictionary representation of the GeoJSON Feature.
        """
        feature_dict = {
            "type": self.type,
            "geometry": self.geometry.to_dict(),
            "properties": self.properties,
        }
        if self.id:
            feature_dict["id"] = self.id
        return feature_dict

    def to_geojson(self):
        """
        Convert the GeoJSON Feature object to a GeoJSON string.

        :return: GeoJSON string representation of the Feature.
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, feature_dict):
        """
        Create a GeoJSONFeature instance from a GeoJSON dictionary.

        :param feature_dict: Dictionary representing a GeoJSON Feature or FeatureCollection.
        :return: GeoJSONFeature instance or list of GeoJSONFeature instances if FeatureCollection.
        """
        if feature_dict["type"] == "FeatureCollection":
            features = []
            for feature in feature_dict["features"]:
                geometry = GeoJSONGeometry.from_dict(feature["geometry"])
                properties = feature.get("properties", {})
                idv = feature.get("id")
                features.append(cls(geometry, properties, idv))
            return features
        else:
            geometry = GeoJSONGeometry.from_dict(feature_dict["geometry"])
            properties = feature_dict.get("properties", {})
            idv = feature_dict.get("id")
            return cls(geometry, properties, idv)

    def __getitem__(self, key):
        """
        Get item from the properties dictionary.

        :param key: Key to retrieve.
        :return: Value corresponding to the key.
        """
        return self.properties[key]

    def __setitem__(self, key, value):
        """
        Set item in the properties dictionary.

        :param key: Key to set.
        :param value: Value to set.
        """
        self.properties[key] = value

    def __eq__(self, other):
        return self.geometry.to_dict() == other.geometry.to_dict()


class GeoJSONGeometry:
    """
    Represents a GeoJSON Geometry object.

    :param type: The type of geometry.
    :param coordinates: The coordinates of the geometry.
    """

    def __init__(self, type, coordinates):
        self.type = type
        self.coordinates = coordinates

    def to_dict(self):
        """
        Convert the GeoJSON Geometry object to a dictionary.

        :return: Dictionary representation of the GeoJSON Geometry.
        """
        return {"type": self.type, "coordinates": self.coordinates}

    def get_coordinates(self):
        """
        Get the coordinates of the point.

        :return: Coordinates of the point.
        """
        return self.coordinates

    @classmethod
    def from_dict(cls, geometry_dict):
        """
        Create a GeoJSONGeometry instance from a GeoJSON dictionary.

        :param geometry_dict: Dictionary representing a GeoJSON Geometry.
        :return: GeoJSONGeometry instance.
        """
        geometry_type = geometry_dict["type"]
        geometry_class = geometry_mapping.get(geometry_type, GeoJSONGeometry)
        return geometry_class(geometry_dict["coordinates"])

    @classmethod
    def init_sub(cls, geometry_type, coordinates):
        """
        Initialize the corresponding subclass based on the geometry type.

        :param geometry_dict: Dictionary representing a GeoJSON Geometry.
        :return: Corresponding subclass of GeoJSONGeometry.
        """
        geometry_class = geometry_mapping.get(geometry_type, GeoJSONGeometry)
        return geometry_class(coordinates)

    def __repr__(self):
        return f"{self.get_coordinates()}, {self.type}"


class GeoJSONPoint(GeoJSONGeometry):
    """
    Represents a GeoJSON Point geometry.

    :param coordinates: The coordinates of the point.
    """

    def __init__(self, coordinates):
        super().__init__("Point", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the point.

        :return: Coordinates of the point.
        """
        return tuple(self.coordinates)


class GeoJSONMultiPoint(GeoJSONGeometry):
    """
    Represents a GeoJSON MultiPoint geometry.

    :param coordinates: The coordinates of the multipoint.
    """

    def __init__(self, coordinates):
        super().__init__("MultiPoint", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the multipoint.

        :return: Coordinates of the multipoint.
        """
        return [tuple(coord) for coord in self.coordinates]


class GeoJSONLineString(GeoJSONGeometry):
    """
    Represents a GeoJSON LineString geometry.

    :param coordinates: The coordinates of the linestring.
    """

    def __init__(self, coordinates):
        super().__init__("LineString", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the linestring.

        :return: Coordinates of the linestring.
        """
        return [tuple(coord) for coord in self.coordinates]


class GeoJSONMultiLineString(GeoJSONGeometry):
    """
    Represents a GeoJSON MultiLineString geometry.

    :param coordinates: The coordinates of the multilinestring.
    """

    def __init__(self, coordinates):
        super().__init__("MultiLineString", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the multilinestring.

        :return: Coordinates of the multilinestring.
        """
        return [[tuple(coord) for coord in line] for line in self.coordinates]


class GeoJSONPolygon(GeoJSONGeometry):
    """
    Represents a GeoJSON Polygon geometry.

    :param coordinates: The coordinates of the polygon.
    """

    def __init__(self, coordinates):
        super().__init__("Polygon", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the polygon.

        :return: Coordinates of the polygon.
        """
        return [[tuple(coord) for coord in ring] for ring in self.coordinates]


class GeoJSONMultiPolygon(GeoJSONGeometry):
    """
    Represents a GeoJSON MultiPolygon geometry.

    :param coordinates: The coordinates of the multipolygon.
    """

    def __init__(self, coordinates):
        super().__init__("MultiPolygon", coordinates)

    def get_coordinates(self):
        """
        Get the coordinates of the multipolygon.

        :return: Coordinates of the multipolygon.
        """
        return [
            [[tuple(coord) for coord in ring] for ring in polygon]
            for polygon in self.coordinates
        ]


geometry_mapping = {
    "Point": GeoJSONPoint,
    "MultiPoint": GeoJSONMultiPoint,
    "LineString": GeoJSONLineString,
    "MultiLineString": GeoJSONMultiLineString,
    "Polygon": GeoJSONPolygon,
    "MultiPolygon": GeoJSONMultiPolygon,
}


# example usage:
if __name__ == "__main__":
    point_geometry = GeoJSONGeometry("Point", [100.0, 0.0])
    point_properties = {"name": "Sample Point"}
    point_feature = GeoJSONFeature(geometry=point_geometry, properties=point_properties)

    print(point_feature.geometry)

    with open("output.geojson", "r", encoding="utf8") as f:
        geojson_string = f.read()
        geojson_dict = json.loads(geojson_string)
        feature_from_dict = GeoJSONFeature.from_dict(geojson_dict)

    print(feature_from_dict.geometry)
