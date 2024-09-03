import pytap

import os
import json
import pyperclip

game_path = ""

# Main Usage
pytap.launch("") # Need to do this before doing anything else, initializes a tap
objects = pytap.get_objects()
layers = pytap.get_layers()
scenes = pytap.get_scenes()

def delete_files_in_directory(directory_path):
    try:
        files = os.listdir(directory_path)
        for file in files:
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
            print("All files deleted successfully.")
        return True
    except OSError:
        print("Error occurred while deleting files.")
        return False

delete_files_in_directory(game_path)
pytap.extract_assets(game_path, ".png", 4)

loadingimagelines = []
renderimagelines = []

memory_usage = 0
image_ids = {}


for x in objects[scenes["Scenes"][0]["name"]]:
    scene_objects = objects[scenes["Scenes"][0]["name"]]
    if scene_objects[x]["object_type"] == "Graphic":
        if os.path.exists(game_path + pytap.get_asset_path(scene_objects[x]["asset_path"], ".png")):
            if not layers[scene_objects[x]["layer"]]["scene"] == 0 and memory_usage + pytap.get_asset_size(scene_objects[x]["asset_path"], ".png") < 200000:
                id = scene_objects[x]["id"].replace("-", "")
                id = id.translate(str.maketrans('', '', '0123456789'))
                size = pytap.get_image_dimensions(scene_objects[x]["asset_path"], ".png")
                size = ((size[0] / 1024) * (256 * 4), (size[0] / 768) * (192 * 4))
                path = pytap.get_asset_path(scene_objects[x]["asset_path"], ".png")
                if not path in image_ids:
                    memory_usage = memory_usage + pytap.get_asset_size(scene_objects[x]["asset_path"], ".png")
                    image_ids[path] = id
                    loadingimagelines.append(id + ' = Image.load("' + path + '", VRAM) \n')
                else:
                    id = image_ids[path]

                renderimagelines.append("\tImage.scale(" + id + ", " + str(size[0]) + " * " + str(abs(scene_objects[x]["scale"][0])) + ", " + str(size[1]) + " * " + str(abs(scene_objects[x]["scale"][1])) + ") \n")
                renderimagelines.append("\t" + "screen.blit(SCREEN_DOWN, " + str((scene_objects[x]["position"][0] / 1024) * 256) + " - camerax, " + str((scene_objects[x]["position"][0] / 768) * 192) + " - cameray, " + id + ") \n")


with open(game_path + "/index.lua", "a+") as f:
    f.writelines(loadingimagelines)
    f.write("\ncamerax = 0\ncameray = 0\n\nwhile not Keys.newPress.Start do\n\tControls.read()\n\n\tif Keys.held.Up then cameray = cameray - 2 end\n\tif Keys.held.Down then cameray = cameray + 2 end\n\tif Keys.held.Right then camerax = camerax + 2 end\n\tif Keys.held.Left then camerax = camerax - 2 end\n\n")
    f.writelines(renderimagelines)
    f.write("\n\trender()\nend")

print(memory_usage)