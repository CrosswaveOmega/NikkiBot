import aiohttp
from bs4 import BeautifulSoup
import discord
import requests
import json
import re
import gui


def remove_link_node(data):
    value = data
    if "<" in value:
        subsoup = BeautifulSoup(value, "html.parser")
        value = subsoup.text
    return value


def group_desoup(metadata, data):
    """for dealing with cog infobox groups."""
    desoupeddata = {}
    for e, entry in enumerate(metadata):
        type = entry["type"]
        target = data["value"]
        for i, target in enumerate(data["value"]):
            if type == "header":
                desoupeddata["header"] = target["data"]["value"]
            if type == "data":
                sources = entry["sources"]
                for source, subdata in sources.items():
                    if target["data"]["source"] == source:
                        desoupeddata[source] = (
                            target["data"]["label"],
                            remove_link_node(target["data"]["value"]),
                        )
    return desoupeddata


def desouper(jsondata):
    """for parsing the basic data in the infobox."""
    desouped = {}
    group_soups = {}
    loaded = json.loads(jsondata, strict=False)
    infobox = loaded[0]
    tag_version = infobox["parser_tag_version"]
    data = infobox["data"]
    metadata = infobox["metadata"]
    for e, entry in enumerate(metadata):
        for i, target in enumerate(data):
            targetdata = data[i]
            if targetdata["type"] != entry["type"]:
                continue
            if entry["type"] == "title":
                sources = entry["sources"]
                for source, subdata in sources.items():
                    if targetdata["data"]["source"] == source:
                        desouped[source] = targetdata["data"]["value"]
            if entry["type"] == "image":
                # I'M AT SOUP. I'M AT SOUP. I'M AT SOUP. I'M AT SOUP
                sources = entry["sources"]
                for source, subdata in sources.items():
                    if targetdata["data"][0]["source"] == source:
                        desouped[source] = targetdata["data"][0]["url"]
            if entry["type"] == "group":
                groupmetadata = entry["metadata"]
                desoupeddata = group_desoup(groupmetadata, targetdata["data"])
                group_soups.update(desoupeddata)
    return desouped, group_soups


def extract_manattacks(table_html):
    """Extract the attack tables of a cog miniboss"""
    attacks_data = {}
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")
    # Extract attack names
    attack_names_row = rows[1]
    attack_names = [cell.text.strip() for cell in attack_names_row.find_all("th")[1:]]
    # Extract attack parameters
    for row in rows[2:]:
        cells = row.find_all("td")
        parameter_name = cells[0].text.strip()
        for i, parameter_value in enumerate(cells[1:], start=1):
            attack_name = attack_names[i - 1]
            if attack_name not in attacks_data:
                attacks_data[attack_name] = {}
            attacks_data[attack_name][parameter_name] = parameter_value.text.strip()
    return attacks_data


def extract_attack_table(html_content):
    """Extract the attack tables of a regular cog enemy"""
    html = html_content

    # Extract each table using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="wikitable")

    output = {}
    for table in tables:
        rows = table.find_all("tr")
        # Extract attack name from the first row
        attack_name = rows[0].find("a").text

        # Extract parameters and values from subsequent rows
        params = {}
        for r in rows[1:]:
            parameters = [cell.text.strip() for cell in r.find_all("td")]
            name, value = parameters[0], parameters[1:]
            gui.dprint(name, value)
            if "Limit" in value:
                value.remove("Limit")
            if name == "Level Continued...":
                name = "Level"
            if name not in params:
                params[name] = []
            params[name].extend(value)

        output[attack_name] = params
    return output


def extract_cheat_soup(html):
    "extract the special cheat abilities minibosses have"
    soup = BeautifulSoup(html, "html.parser")
    text_list = []
    text = soup.text
    text_list_raw = text.split("\n")
    for c in text_list_raw:
        if c.strip() and c.strip() != "Cheats[]":
            text_list.append(c.strip())
    # Find the first image tag
    return text_list


def callsoup(params):
    # Send API request
    response = requests.get(
        "https://toontown-corporate-clash.fandom.com/api.php", params=params
    )
    data = response.json()
    return data


def get_cog_soup(page):
    mook_positions = ["Operations Analyst", "Employee", "Field Specialist"]
    miniboss_positions = [
        "Regional Manager",
        "Manager",
        "Contractor",
        "Third Cousin Twice Removed",
        "???",
    ]
    boss_positions = ["Boss"]
    params = {"action": "parse", "page": page, "format": "json", "prop": "sections"}
    data = callsoup(params)
    attack, cheats = None, None
    sections = data["parse"]["sections"]
    for s in sections:
        if s["line"] == "Attacks":
            attack = s["number"]
        if s["line"] == "Cheats":
            cheats = s["number"]

    params = {"action": "parse", "page": page, "format": "json", "section": "0"}
    data = callsoup(params)
    soup, desoup = desouper(data["parse"]["properties"][0]["*"])
    attack_soup = ""
    cheat_soup = ""
    if attack:
        params["section"] = attack
        data = callsoup(params)
        otherlinks = data["parse"]["links"]
        sublink = otherlinks[0]["*"]
        unsortedsoup = data["parse"]["text"]["*"]
        if "Click here to visit the page" in unsortedsoup:
            twosoup = BeautifulSoup(unsortedsoup, "html.parser")
            a_tag = twosoup.find("a", {"title": sublink}, href=True)
            if a_tag:
                href = a_tag["href"]
                foundurl = href.replace("/wiki/", "")
                params["page"] = foundurl
                params.pop("section")
                data = callsoup(params)
            else:
                data = "NoAttacks?"
        if data != "NoAttacks?":
            attack_soup = data["parse"]["text"]["*"]
    if cheats:
        params["section"] = cheats
        data = callsoup(params)
        cheat_soup = data["parse"]["text"]["*"]
    return soup, desoup, attack_soup, cheat_soup


def tform(data: tuple):
    """Format a data tuple"""
    return f"{data[0]}: {data[1]}"


async def formatembed(
    url: str,
    soup: dict,
    desoup: dict,
    attack_soup: str,
    cheat_soup: str,
    foetattle: str = "",
    cheat_tattle: str = "",
):
    mook_positions = ["Operations Analyst", "Employee", "Field Specialist"]
    miniboss_positions = [
        "Regional Manager",
        "Manager",
        "Contractor",
        "Third Cousin Twice Removed",
    ]
    boss_positions = ["Boss"]
    department = desoup.get("department", None)
    link = desoup.get("position", None)
    cogclass = "???"

    deppos = "?"
    man_prelude = ""
    attack_list = []
    spaced = "UNKNOWN"
    if link != None and department != None:
        deppos = f" {tform(link)}\n{tform(department)} "
        classcheck = link[1].strip()
        if classcheck in mook_positions:
            cogclass = "mook"
        elif classcheck in miniboss_positions:
            cogclass = "mini"
        elif classcheck == "Boss":
            cogclass = "boss"
    if cogclass == "mook":
        level_range = f"{desoup['lowest_level'][1]}-{desoup['highest_level'][1]}"
        damage_range = f"{desoup['lowest_damage'][1]}-{desoup['highest_damage'][1]}"

        spaced = f"`Levels: {level_range:<8}`\n`Damage: {damage_range:<8}`"
        attack_data = extract_attack_table(attack_soup)
        for name, param in attack_data.items():
            paramsoup = ""
            for key, values in param.items():
                key = key.strip()
                if key:
                    if "(All Levels)" in key:
                        key = key.replace("(All Levels)", "")
                        key = key.strip()
                    values_str = ", ".join(values)
                    if len(values) > 2:
                        if values[0] == values[-1]:
                            values_str = f"{values[0]}"
                        else:
                            values_str = f"{values[0]}-{values[-1]}"
                    paramsoup += f"{key}: {values_str}\n"
            attack_list.append((name, paramsoup))
    if cogclass == "mini":
        man_prelude = f"Real Name: {desoup['Honorifics'][1]} {desoup['real_name'][1]}"
        damage_range = f"{desoup['lowest_damage'][1]}-{desoup['highest_damage'][1]}"

        spaced = f"Level: {desoup['level'][1]}\nHP:  {desoup['hp'][1]}\nDefense: {desoup['defense'][1]}\nDamage: {damage_range:<8}"
        attack_data = extract_manattacks(attack_soup)
        for name, param in attack_data.items():
            paramsoup = ""
            for key, values in param.items():
                key = key.strip()
                if key:
                    paramsoup += f"{key}: {values}\n"
            attack_list.append((name, paramsoup))

    if cogclass == "boss":
        man_prelude = f"Real Name: {desoup['real_name'][1]}"
        level_range = f"{desoup['lowest_level'][1]}-{desoup['highest_level'][1]}"
        damage_range = f"{desoup['lowest_damage'][1]}-{desoup['highest_damage'][1]}"

        spaced = f"`Levels: {level_range:<8}`\n`Damage: {damage_range:<8}`"
        attack_data = extract_manattacks(attack_soup)

    if cogclass in ["mook", "mini", "boss"]:
        embed = discord.Embed(
            title=soup["title1"],
            description=f"{man_prelude}\n{tform(link)}\n{tform(department)} \n"
            + foetattle,
            color=discord.Color(0x8AC637),
            url=url,
        )
        embed.set_author(name="Nikki's Cog Spy")

        embed.add_field(name="Level and Damage Range", value=f"{spaced}", inline=True)
        embed.add_field(
            name="Likes/Dislikes",
            value=f"{tform(desoup['likes'])}\n{tform(desoup['dislikes'])}",
            inline=True,
        )
        attacks = ""

        if len(attack_data.keys()) > 5:
            attacks = "**NO REFUGE, BE ATTITUDE FOR GAINS!**"
        embed.add_field(name="Attacks", value=attacks, inline=False)
        for attacktup in attack_list:
            name, text = attacktup
            embed.add_field(name=name, value=f"{text}", inline=True)

        if cheat_tattle:
            gui.dprint(cheat_tattle)
            embed.add_field(
                name=f"Cheat Tattle", value=cheat_tattle[:1020], inline=False
            )

        embed.set_thumbnail(url=soup["image1"])
        return embed
