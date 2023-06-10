import os
import configparser
import json
import gui
from typing import Optional

DEFAULT_ASSETS = {
    "main":{
        "name": "TCBOT",
        'homeguild': 0
    },
    "lists":{
        'default':[],
        'blanknames':["Alice", "Bob", "Charlie", "David", "Eve",'Aspen', 'Avery', 'Blake', 'Charlie', 'Chris', 'Ellis', 'Emerson', 'Frankie', 'Gray', 'Harper', 'Hayden', 'Indigo', 'Jamie', 'Kendall', 'Lane', 'Parker', 'River', 'Robin', 'Sage', 'Scout', 'Sidney', 'Skylar', 'Taylor', 'Terry', 'Tyler', 'Wren', 'Ash', 'Bay', 'Emory', 'Harley', 'Hollis', 'Jessie', 'Marley', 'Nat', 'Payton', 'Sky', 'Stevie', 'Tracy', 'Whitney', 'Winter', 'Cam', 'Casey', 'Dana', 'Finley', 'Pat', 'Quinn', 'Riley', 'Rowan', 'Ryan', 'Arin', 'Blaine', 'Cary', 'Darcy', 'Devan', 'Kerry', 'Sean', 'Teagan', 'Arian', 'Ariel', 'Asher', 'Eden', 'Eli', 'Gabriel', 'Sam', 'Zion', 'Ira', 'Jayden', 'Jordan', 'Yael', 'Jules', 'Dominique', 'Noel', 'Remy', 'Alex', 'Nico', 'Phoenix', 'Kris', 'Blair', 'Kamryn', 'Cameron', 'Leslie', 'Morgan', 'Reese', 'Ali', 'Amal', 'Logan', 'Rory', 'Tristan', 'Lee', 'Kai', 'Armani', 'Luca', 'Akira', 'Aki', 'Kim', 'Adrian', 'Val', 'Sasha', 'Amari', 'Max', 'Asha', 'Dakota']
    },
    "urls":{
        'generic': "https://example.com/image.png",
        'default': "https://example.com/image.png",
        'embed_icon':'https://example.com/image.png'
    }
}


class AssetLookup:
    _assets = {}
    def __init__(self):
        self.load_assets()
    
    @staticmethod
    def load_assets(config_path="assets.conf"):
        if os.path.exists(config_path):
            parser = configparser.ConfigParser()
            parser.read(config_path)
            for section in parser.sections():
                AssetLookup._assets[section] = dict(parser.items(section))

            # Check if default assets are present, and add them if they're not
            for section, assets in DEFAULT_ASSETS.items():
                if section not in AssetLookup._assets:
                    gui.gprint(f"section {section} not found in assets.conf")
                    AssetLookup._assets[section] = assets
                else:
                    for asset, default_value in assets.items():
                        if asset not in AssetLookup._assets[section]:
                            gui.gprint(f"asset {asset} not found in section{section}")
                            AssetLookup._assets[section][asset] = default_value
        else:
            AssetLookup._assets = DEFAULT_ASSETS
            AssetLookup.save_assets(config_path)


    @staticmethod
    def set_asset(asset_name: str, value: str, category: Optional[str] = None):
        if category is not None:
            AssetLookup._assets.setdefault(category, {})
            AssetLookup._assets[category][asset_name] = value
        else:
            for assets in AssetLookup._assets.values():
                assets[asset_name] = value
    @staticmethod
    def save_assets(config_path="assets.conf"):
        parser = configparser.ConfigParser()
        for section, assets in AssetLookup._assets.items():
            parser[section] = assets
        with open(config_path, 'w') as f:
            parser.write(f)

    @staticmethod
    def get_defaultfallback(asset_name: str, category: str):
        if category is None:
            for assets in DEFAULT_ASSETS.values():
                if asset_name in assets:
                    return assets[asset_name]
        else:
            if asset_name in DEFAULT_ASSETS.get(category, {}):
                return DEFAULT_ASSETS[category][asset_name]
    @staticmethod
    def get_fallback(asset_name: str, category: Optional[str] = None):
        if category is None:
            if asset_name in AssetLookup._assets:
                return AssetLookup._assets[asset_name]['default']
        else:
            if asset_name in  AssetLookup._assets[category]:
                return AssetLookup._assets[category]['default']
        return None

    @staticmethod
    def get_asset(asset_name: str, category: Optional[str] = None):
        if category is not None and asset_name in AssetLookup._assets[category]:
            return AssetLookup._assets[category][asset_name]
        elif category is None:
            for assets in AssetLookup._assets.values():
                if asset_name in assets:
                    return assets[asset_name]
        fallback = AssetLookup.get_fallback(asset_name, category)
        if fallback is None:
            default=AssetLookup.get_defaultfallback(asset_name,category)
            if default is None:
                raise ValueError(f"No asset found for '{asset_name}' in category '{category}'")
            
        return fallback