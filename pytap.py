import zipfile
import plistlib
import json
import io
import os
import sqlite3
import base64
import tempfile
from plistlib import UID
from PIL import Image

tap_data = {}
level_json = {}

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UID):
            return obj.data
        if isinstance(obj, bytes):
            try:
                # Try to decode bytes as utf-8
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                # If it fails, encode bytes as base64
                return base64.b64encode(obj).decode('utf-8')
        return super().default(obj)

def decode_bplist_base64(base64_string):
    """Decode a Base64 encoded bplist string."""
    return base64.b64decode(base64_string)

def parse_bplist(bplist_data):
    """Parse the bplist data into a Python dictionary."""
    return plistlib.loads(bplist_data)

def process_data(data):
    """Recursively process the data to make it JSON serializable."""
    if isinstance(data, dict):
        return {key: process_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [process_data(item) for item in data]
    elif isinstance(data, bytes):
        try:
            # Try to decode bytes as utf-8
            return data.decode('utf-8')
        except UnicodeDecodeError:
            # If it fails, encode bytes as base64
            return base64.b64encode(data).decode('utf-8')
    elif isinstance(data, UID):
        return data.data
    else:
        return data

def convert_to_json(parsed_data):
    """Convert parsed data to JSON format."""
    processed_data = process_data(parsed_data)
    return json.dumps(processed_data, indent=4, cls=CustomEncoder)

def convert_bplist_to_json(bplist, fix):
        base64_string = bplist

        bplist_data = decode_bplist_base64(base64_string)
        parsed_data = parse_bplist(bplist_data)
        json_data = json.loads(convert_to_json(parsed_data))

        if not fix:
            bplist_data = decode_bplist_base64(json_data["$objects"][1]["NS.data"])
        else:
            bplist_data = decode_bplist_base64(json_data["$objects"][1])
        
        parsed_data = parse_bplist(bplist_data)
        json_data = json.loads(convert_to_json(parsed_data))

        final_json = {}
        index = 0
        for x in json_data["$objects"][1]["NS.keys"]:
            final_json[str(json_data["$objects"][x])] = json_data["$objects"][json_data["$objects"][1]["NS.objects"][index]]
            index = index + 1

        types = ["NS.rectval", "NS.sizeval", "NS.pointval", "NSColorSpace", "value", "controlledBy", "valueKey"]
        for y in final_json:
            if type(final_json[y]) == dict:
                for n in final_json[y]:
                    new_value = final_json[y][n]
                    if n in types:
                        new_value = json_data["$objects"][final_json[y][n]]
                    elif n == "NS.keys":
                        ns_json = {}
                        index = 0
                        for x in final_json[y]["NS.keys"]:
                            if type(json_data["$objects"]) == 'dict':
                                ns_json[str(json_data["$objects"][x])] = json_data["$objects"][final_json[y]["NS.objects"][index]]
                            index = index + 1
                        new_value = ns_json

                        for s in new_value:
                            if s in types:
                                new_value[s] = json_data["$objects"][final_json[y][s]]
                    elif n == "NS.objects":
                        ns_json = {}
                        index = 0
                        for x in final_json[y]["NS.objects"]:
                            if type(json_data["$objects"]) == 'dict':
                                ns_json[str(json_data["$objects"][x])] = json_data["$objects"][final_json[y]["NS.objects"][index]]
                            index = index + 1
                        new_value = ns_json
                    final_json[y][n] = new_value

        return final_json

def convert_sqlite_to_json(db_bytes):
    # Write the bytes to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_db:
        temp_db.write(db_bytes)
        temp_db_path = temp_db.name

    # Connect to the SQLite database
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Get the list of tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    db_data = {}

    # Iterate over tables and fetch all rows
    for table_name in tables:
        table_name = table_name[0]
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Get the column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        column_info = cursor.fetchall()
        columns = [info[1] for info in column_info]

        # Convert table data to list of dictionaries
        table_data = []
        for row in rows:
            row_dict = {}
            for idx, col in enumerate(columns):
                value = row[idx]
                if isinstance(value, bytes):
                    value = base64.b64encode(value).decode('utf-8')
                row_dict[col] = value
            table_data.append(row_dict)

        db_data[table_name] = table_data

    # Close the database connection
    conn.close()

    json_data = db_data
    return json_data

def convert_plist_to_json(plist):
    # Read the .plist file
    with io.BytesIO(plist) as plist_io:
        plist_data = plistlib.load(plist_io)

    json_data = plist_data
    return json_data


# Actual Module Stuff

def launch(tap):
    global tap_data
    tap_data = zipfile.ZipFile(tap, 'r')
    global level_json
    level_json = convert_sqlite_to_json(tap_data.read('levels/Level 1/Level.sqlite'))
    return convert_bplist_to_json(level_json["ZBEHAVIOURDATA"][0]["ZACTIONS"], True)

def get_game_details():
    game_details = convert_plist_to_json(tap_data.read('gameDetails.plist'))
    return game_details

def get_level_details():
    level_details = convert_plist_to_json(tap_data.read('levels/Level 1/levelDetails.plist'))
    return level_details

def get_scenes():
    scenes = []
    overlays = []
    for s in level_json["ZLEVELDATA"]:
        if s["ZSCENETYPE"] == 0:
            scenes.append(
                    {
                        "name": s["ZLEVELNAME"],
                        "position": (s["ZX_POS"], s["ZY_POS"]),
                        "zoom": s["ZSCALE"],
                        "preload": s["ZPRELOAD"]
                    }
                )
        else:
            overlays.append(
                    {
                        "name": s["ZLEVELNAME"],
                        "position": (s["ZX_POS"], s["ZY_POS"]),
                        "zoom": s["ZSCALE"],
                        "preload": s["ZPRELOAD"]
                    }
                )

    return {"Scenes": scenes, "Overlays": overlays}

def get_objects():
    objects = []
    objects_organised = {}

    levels = []
    for s in level_json["ZLEVELDATA"]:
        levels.append(s["ZLEVELNAME"])

    asset_paths = {}
    for p in level_json["ZPATHDATA"]:
        asset_paths[p["ZUNIQUEID"]] = p["ZPATH"]

    layer_scenes = {}
    for l in level_json["ZLAYERDATA"]:
        if not l["ZLEVEL"]:
            layer_scenes[l["Z_PK"]] = 0
        else:
            layer_scenes[l["Z_PK"]] = l["ZLEVEL"]


    object_positions = {}
    for x in level_json["ZOBJECTPOSITION"]:
        object_positions[x["ZOBJECTS"]] = x

    for x in level_json["ZOBJECTDATA"]:
        object_details = x
        pk = object_details["Z_PK"]
        if pk in object_positions:
            object_secondary_details = object_positions[pk]
            ui_element = False
            layer = object_secondary_details["ZLAYERS"]
            if not layer:
                layer = 1
            if object_secondary_details["ZUNITX"] == 2:
                ui_element = True

            path = None
            if object_details["ZPATH"]:
                path = asset_paths[object_details["ZPATH"]]

            object_data = convert_bplist_to_json(str(object_details["ZGAMEOBJECTDATA"]), False)

            collision_type = object_data["shape"]
            collision_points = []
            for x in level_json["ZCOLLISIONDATA"]:
                if x["ZOBJECT"] == pk:
                    collision_points.append((0, 0))
            for y in level_json["ZCOLLISIONDATA"]:
                if y["ZOBJECT"] == pk:
                    collision_points[y["ZINDEX"]] = (y["ZX_POS"], -y["ZY_POS"])

            print(layer_scenes)

            object_data = {
                "name": object_details["ZNAME"],
                "ui_element": ui_element,
                "position": (object_secondary_details["ZX"], object_secondary_details["ZY"]),
                "scale": (object_details["ZX_SCALE"], object_details["ZY_SCALE"]),
                "rotation": object_details["ZROTATION"],
                "anchor": (object_secondary_details["ZANCHORX"], object_secondary_details["ZANCHORY"]),
                "gravity": (object_details["ZGRAVITY_X"], object_details["ZGRAVITY_Y"]),
                "friction": object_details["ZFRICTION"],
                "mass": object_details["ZMASS"],
                "denisty": object_details["ZDENSITY"],
                "restitution": object_details["ZRESTITUTION"],
                "physics_mode": object_details["ZPHYSICS_MODE"],
                "object_type": object_details["ZOBJECTTYPE"],
                "collidable": object_details["ZCOLLIDABLE"],
                "id": object_details["ZUNIQUEID"],
                "asset_path": path,
                "gameobjectdata": object_data,
                "collision_points": collision_points,
                "collision_shape": collision_type,
                "z_index": object_details["ZZ_INDEX"],
                "flip": (object_details["ZFLIPX"], object_details["ZFLIPY"]),
                "layer": int(layer),
                "scene": int(layer_scenes[layer])
            }

            objects.append(object_data)

    global_ui_objects = {}
    for x in objects:
        last_scene = None

        print(levels)
        if x["scene"] == 0:
            global_ui_objects[x["id"]] = x
        else:
            if len(levels) > x["scene"] - 1:
                if levels[x["scene"] - 1] in objects_organised:
                    objects_organised[levels[x["scene"] - 1]][x["id"]] = x
                else:
                    objects_organised[levels[x["scene"] - 1]] = {x["id"]: x}

                last_scene = levels[x["scene"] - 1]
            else:
                if last_scene in objects_organised:
                    objects_organised[last_scene][x["id"]] = x
                else:
                    objects_organised[last_scene] = {x["id"]: x}
    for x in objects_organised:
        for y in global_ui_objects:
            objects_organised[x][y] = global_ui_objects[y]

    return objects_organised

def get_behaviours():
    objectspk = {}
    for x in level_json["ZOBJECTDATA"]:
        objectspk[x["Z_PK"]] = x

    behaviours_organised = {}
    for x in level_json["ZBEHAVIOURDATA"]:
        behaviour = {}
        actions = convert_bplist_to_json(x['ZACTIONS'], True)
        outputs = None
        if "outputs" in actions:
            outputs = actions["outputs"]["NS.objects"]

        actions["outputs"] = outputs
        actions["behaviourCategory"] = actions["behaviourCategory"]["NS.string"]
        behaviour["actions"] = actions
        behaviour["root"] = x["ZISROOT"]
        behaviour["name"] = x["ZNAME"]
        behaviour["tag"] = x["ZTAG"]
        behaviour["position"] = (x["ZX_POS"], x["ZY_POS"])

        if objectspk[x["ZOBJECT"]]["ZUNIQUEID"] in behaviours_organised:
            behaviours_organised[objectspk[x["ZOBJECT"]]["ZUNIQUEID"]].append(behaviour)
        else:
            behaviours_organised[objectspk[x["ZOBJECT"]]["ZUNIQUEID"]] = [behaviour]
    
    return behaviours_organised

def extract_assets(to, format, compress = 0):
    name = None
    for file in tap_data.filelist:
        if file.filename.endswith(format):
            name = file.filename

            try:
                tap_data.extract(name, to)

                if not compress == 0:
                    image = Image.open(to + name)
                    width, height = image.size
                    new_size = (int(width / compress), int(height / compress))
                    resized_image = image.resize(new_size)
                    resized_image.save(to + name, optimize=True, quality=50)
            except Exception as e:
                print(f"Error extracting {name}: {e}")
                pass

def get_asset_path(path, format, get_hd = False):
    for file in tap_data.filelist:
        if file.filename.startswith(path) and file.filename.endswith(format):
            if get_hd:
                if file.filename.endswith("-hd.png"):
                    return file.filename
            else:
                if not file.filename.endswith("-hd.png") and not file.filename.endswith(".thumbnail.png"):
                    return file.filename

def get_image_dimensions(path, format, get_hd = False):
    for file in tap_data.filelist:
        if file.filename.startswith(path) and file.filename.endswith(format):
            if get_hd:
                if file.filename.endswith("-hd.png"):
                    with tap_data.open(file.filename) as image_file:
                        image = Image.open(image_file)
                        width, height = image.size
                        return (width, height)
            else:
                if not file.filename.endswith("-hd.png") and not file.filename.endswith(".thumbnail.png"):
                    with tap_data.open(file.filename) as image_file:
                        image = Image.open(image_file)
                        width, height = image.size
                        return (width, height)
            
def get_asset_size(path, format, get_hd = False):
    for file in tap_data.filelist:
        if file.filename.startswith(path) and file.filename.endswith(format):
            if get_hd:
                if file.filename.endswith("-hd.png"):
                    return file.file_size
            else:
                if not file.filename.endswith("-hd.png") and not file.filename.endswith(".thumbnail.png"):
                    return file.file_size
    
def get_layers():
    layers = {}
    for l in level_json["ZLAYERDATA"]:
        scene = 0
        if l["ZLEVEL"]:
            scene = l["ZLEVEL"]
        ui_layer = False
        if not l["ZNAME"]:
            ui_layer = True

        layers[l["Z_PK"]] = {"scene": scene, "ui_layer": ui_layer}
    return layers
        

def get_project():
    scenes = get_scenes()
    return {"Behaviours": get_behaviours(), "Objects": get_objects(), "Scenes": scenes["Scenes"], "Overlays": scenes["Overlays"], "GameDetails": get_game_details(), "LevelDetails": get_level_details(), "Layers": get_layers()}