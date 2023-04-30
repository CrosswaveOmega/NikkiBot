import os
import configparser

from typing import Optional
DEFAULT_ASSETS = {
    "main":{
        "name": "TCBOT"
    },
    "urls":{
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
                    AssetLookup._assets[section] = assets
                else:
                    for asset, default_value in assets.items():
                        if asset not in AssetLookup._assets[section]:
                            AssetLookup._assets[section][asset] = default_value
        else:
            AssetLookup._assets = DEFAULT_ASSETS
            AssetLookup.save_assets(config_path)

    @staticmethod
    def save_assets(conf_path: str):
        parser = configparser.ConfigParser()
        for section, assets in AssetLookup._assets.items():
            parser[section] = assets
        with open(conf_path, 'w') as f:
            parser.write(f)

    @staticmethod
    def get_fallback(asset_name: str, category: str):
        if category is None:
            for assets in DEFAULT_ASSETS.values():
                if asset_name in assets:
                    return assets[asset_name]
        else:
            if asset_name in DEFAULT_ASSETS.get(category, {}):
                return DEFAULT_ASSETS[category][asset_name]

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
            raise ValueError(f"No asset found for '{asset_name}' in category '{category}'")
        return fallback