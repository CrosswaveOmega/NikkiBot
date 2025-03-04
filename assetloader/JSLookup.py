import os

from typing import Optional

from javascriptasync import JSContext


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
    async def get_full_pathas(filename: str, alias: str, jsenv: JSContext):
        js_folder = "../js/" + filename
        myfile = await jsenv.require_a(js_folder, amode=True, store_as=alias)
        return myfile
