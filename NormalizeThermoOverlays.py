import json
import os
import argparse

KELVIN = 273.15

def find_temp_range(file_names):
    # find the temperature range accross all images
    max_temp, min_temp = None, None
    for name in file_names:
        with open((json_files_path+ '/' + name), 'r') as f:
            metadata = json.loads(f.read())
            max_temp_this_image = int(metadata["RawValueMedian"]) + int(metadata["RawValueRange"])/2
            min_temp_this_image = max_temp_this_image - int(metadata["RawValueRange"])
            max_temp = max(max_temp, max_temp_this_image)
            min_temp = max(min_temp, min_temp_this_image)
            #max_temp = max(max_temp, int(metadata["ImageTemperatureMax"])) # None handled implicitly
            #if min_temp is None or int(metadata["ImageTemperatureMin"]) < min_temp:
            #    min_temp = int(metadata["ImageTemperatureMin"])

    return (max_temp - KELVIN), (min_temp - KELVIN)


def process_files(relevant_path):
    json_file_names = [fn for fn in os.listdir(relevant_path)
                  if fn.endswith('json')]
    print "json files: " + str(json_file_names) 

    temp_range = find_temp_range(json_file_names)
    print temp_range

if __name__ == "__main__":
    # parse command line args
    parser = argparse.ArgumentParser(description="Normalize thermo overlay accross all images")
    parser.add_argument('--json_path', '-j', default='json_files/')
    parser.add_argument('--csv_path', '-c', default='json_files/')
    args = parser.parse_args()

    json_files_path = args.json_path
    csv_files_path = args.csv_path
    process_files(json_files_path)
