import os
import configparser
import json

from typing import Optional

from javascriptasync import require_a, require

class JavascriptLookup:
    @staticmethod
    def find_javascript_file(filename: str, appendwith: Optional[str] = None):
        js_folder = "./js"

        if not os.path.exists(js_folder):
            os.makedirs(js_folder)

        file_path = os.path.join(js_folder, filename)

        if os.path.exists(file_path):
            script = ""
            with open(file_path, "r", encoding="utf8") as file:
                script = file.read()
            if appendwith:
                script += "\n" + appendwith
            return script
        else:
            return None

    @staticmethod
    async def get_full_pathas(filename: str):
        #test=require("@mozilla/readability")
        print('ok')
        js_folder = "../js/"+filename
        myfile=await require_a(js_folder,amode=True)
        print("clear")
        return myfile
    
