#Here we attempt to define a function for converting FLIR Images to various states
#the based on the flir.php calculations
#http://u88.n24.queensu.ca/exiftool/forum/index.php/topic,4898.msg23972.html#msg23972
#http://u88.n24.queensu.ca/exiftool/forum/index.php/topic,4898.msg24230.html#msg24230
#http://130.15.24.88/exiftool/forum/index.php?topic=4898.90
#http://www.eevblog.com/forum/thermal-imaging/flir-e4-thermal-imaging-camera-teardown/msg342072/#msg342072
#
#
# The following can be installed on MacOS using brew (e.g. brew install imagemagick)
# -- Required Command Line Tools --
# exiftools
# imagemagick
#
# -- Instruction for running on Mac --
# Place this file in the same directory as the thermo images you'd like to process, then run the program with no arguments
# ~$ python ConvertRawToCsv.py
# The resulting files will be places in the same directory
#
# use option -n to normalize the images

#TODO: Put the Exif Data Back in the Final Image?
#TODO: Make the input image dimension and the output dimensions match?
#TODO: How does resampling work when the resize command is executed? Is resampling the right term?
#TODO: Investigate "Warning: [minor] Possibly incorrect maker notes offsets (fix by 12?) - IMG_1212" that happens on all images. (Study Data)
#TODO: Investigate "Warning: GPS pointer references previous ExifIFD directory - IMG_3909.JPG" that seems to happen with this image. (Pilot Data)
#TODO: Figure out if we can (and how) process Lepton Images with the same scripts?

#Standard Imports
from PIL import Image
from PIL.ExifTags import TAGS
import subprocess
from subprocess import check_call
import re
import math
import os.path
import os
import argparse

import time # for performance profiling


#ImageMagick 7 uses alpha-color; older uses mattecolor"
#alpha_color = "mattecolor"
alpha_color = "alpha-color"
VERSION = 2     # increment this if the files created change
Android = True

#Get EXIF Data
#https://pypi.python.org/pypi/ExifRead/2.1.2
def getExifData(img):
    ret = {}
    i = Image.open(img)
    info = i._getexif()

    #Extracting and Processing Standard Image metadata
    for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded != 'MakerNote':
                ret[decoded] = value

    #Extracting FLIR Image metadata
    print 'exiftool -php -q '+ img
    proc = subprocess.Popen(['exiftool', '-php', '-q', img], stdout=subprocess.PIPE)
    exifRawData = proc.stdout.read()
    exifRawData = str(exifRawData).split(',')

    #Processing FLIR Image metadata
    for element in exifRawData:
        element = str(element)
        element = re.sub(r'.*?"', '"', element, count=1)
        element = re.sub(r'"', '', element)
        element = ' '.join(element.split(",'")[0].strip().split())
        
        if (element != ''):
            if (len(element.split(' => ')) >= 2):
                key = element.split(' => ')[0]
                val = element.split(' => ')[1]
                ret[key] = val
            elif (len(element.split(' => ')) == 1):
                key = element.split(' => ')[0]
                val = "NIL"
                ret[key] = val
    return ret

def convert_pixel(targ, exifData):
    # Heat conversion (Celcius)
    R1 = float(exifData['PlanckR1'])
    R2 = float(exifData['PlanckR2'])
    B = float(exifData['PlanckB'])
    O = float(exifData['PlanckO'])
    F = float(exifData['PlanckF'])

    # Calculate Atmospheric Transmission
    Temp_atm = float(str(exifData['AtmosphericTemperature']).split('C')[0])
    Distance = float(str(exifData['ObjectDistance']).split('m')[0])
    Humidity = float(str(exifData['RelativeHumidity']).split('%')[0])
    H2o = (Humidity/100) * math.exp(1.5587 + 6.939e-2 * Temp_atm - 2.7816e-4 * pow(Temp_atm,2) + 6.8455e-7 * pow(Temp_atm,3));

    # Get displayed temp range in RAW values
    RAWatm = R1/(R2 *(math.exp(B/(Temp_atm+273.15))-F))-O;
    RAWmax = float(exifData['RawValueMedian']) + (float(exifData['RawValueRange'])/2)
    RAWmin = RAWmax - float(exifData['RawValueRange'])
    RAWtarg = float(targ)

    # Calc amount of radiance of reflected objects ( Emissivity < 1 )
    Temp_ref = float(exifData['ReflectedApparentTemperature'].split('C')[0])
    RAWrefl = R1 /( R2*(math.exp(B /(Temp_ref+273.15)) - F)) - O

    # Get displayed object temp max/min and convert to "%.1f" for printing
    Emissivity = float(exifData['Emissivity'])
    RAWmaxobj = (RAWmax - (1 - Emissivity)* RAWrefl)/Emissivity
    RAWminobj = (RAWmin - (1 - Emissivity) * RAWrefl)/Emissivity
    RAWtargobj = (RAWtarg - (1 - Emissivity) * RAWrefl)/Emissivity
    ret = round(float(B/math.log(R1/(R2 * (RAWtargobj + O)) + F)-273.15), 1)
    print ret
    return ret

def print_exifData(meta):
    print("Array Contains: " + str(len(meta)) + " Items")
    print("{" + "\n".join("{}: {}".format(k, v) for k, v in sorted(meta.items())) + "}")
    return 0

def create_palette_file(pal, file, name, meta):
    #Variables
    font_color = 'white'
    frame_color = 'black'
    #font = '-font C:\Windows\Fonts\segoe_0.ttf'
    #TODO: Add posix font
    font = '-font C:\Windows\Fonts\segoeui.ttf'

    #Temperature Range
    Max = float(meta['RawValueMedian'])+float(meta['RawValueRange'])/2 # <-- DEBUG shouldn't that be avg not median?
    Min = Max-float(meta['RawValueRange'])
    Cmax = convert_pixel(Max, meta)
    Cmin = convert_pixel(Min, meta)

    #Create Palette
    check_call('exiftool '+ file +' -b -Palette | convert -size "' + meta['PaletteColors'] \
               + 'X1" -depth 8 YCbCr:- -separate -swap 1,2 -set colorspace YCbCr -combine -colorspace sRGB -auto-level ' + pal, shell=True)

    #Color Scale
    check_call('convert -size 16x430 gradient: ' + pal + ' -clut -' + alpha_color + ' ' + font_color \
               + ' -frame 1x1 -set colorspace rgb -' + alpha_color + ' gray -frame 1x1 "'+name+'_gradient.png"', shell=True);
    check_call('convert '+name+'_gradient.png -background ' + frame_color + ' ' + font + ' -fill ' + font_color \
               + ' -pointsize 15 label:\"' + str(Cmax) + ' C\" +swap -gravity Center -append  label:\"' + str(Cmin) + ' C\" -append '+name+'_gradient.png', shell=True)
    return 0

# Gets range of temperatures accross all thermo images, depends on existence of json files
def get_temperature_range(exifDataAll):
    # find the temperature range accross all images
    max_temp, min_temp = None, None
    for metadata in exifDataAll.values():
        max_temp_this_image = int(metadata["RawValueMedian"]) + int(metadata["RawValueRange"])/2
        min_temp_this_image = max_temp_this_image - int(metadata["RawValueRange"])
        max_temp = max(max_temp, max_temp_this_image)
        min_temp = max(min_temp, min_temp_this_image)

    return max_temp, min_temp

# Calculates metadata used by the extract_raw_data(...) function
# Depends on the values it extracts from meta being the same accross all images
def calc_extract_raw_data_meta_info(meta):
    global Max, Min, R1, R2, B, O, F, Smax, Smin, Sdelta
    # Set max and min temperature of the image for coloring
    if args.normalize: # remove False to restore this option
        Max, Min = TEMP_RANGE
    else:
        Max = float(meta['RawValueMedian'])+float(meta['RawValueRange'])/2
        Min = Max-float(meta['RawValueRange'])

    R1 = float(meta['PlanckR1'])
    R2 = float(meta['PlanckR2'])
    B = float(meta['PlanckB'])
    O = float(meta['PlanckO'])
    F = float(meta['PlanckF'])

    Smax=B/math.log(R1/(R2*(Max+O))+F);
    Smin=B/math.log(R1/(R2*(Min+O))+F);
    Sdelta=Smax-Smin;
    
# Extract raw thermo data into a thermo png file 
def extract_raw_data(file, outName, meta, no_endian):
    #16 bit PNG (Get Raw Thermal Values)
    resize = "-resize 200%"
    size = str(meta['RawThermalImageWidth']) + "x" + str(meta['RawThermalImageHeight']);
    if no_endian:
        check_call(str('exiftool -b -RawThermalImage '+file+' | convert - gray:- | convert -depth 16 -size '+size+'  gray:- '+outName+'_raw.png'), shell=True)
    else:
        check_call(str('exiftool -b -RawThermalImage '+file+' | convert - gray:- | convert -depth 16 -endian msb -size '+size+'  gray:- '+outName+'_raw.png'), shell=True)
        
    check_call('convert '+outName+'_raw.png -fx \"('+str(B)+'/ln('+str(R1)+'/('+str(R2)+'*((65535*u+'+str(O)+')?(65535*u+'+str(O)+'):1))+' \
               +str(F)+')-'+str(Smin)+')/'+str(Sdelta)+'\" '+outName+'_ir.png', shell=True)
    
    return 0

# Extract the embedded rgb data from the FLIR thermo image to a png
def extract_embedded_file(file, outName, dat):
    #Get Embedded Image
    if dat:
        check_call('exiftool '+file+' -embeddedimage -b | convert -size 480x640 -depth 8 ycbcr:- '+outName+'_embedded.png', shell=True)
    else:
        check_call('exiftool -b -EmbeddedImage '+file+' > '+outName+'_embedded.png', shell=True)
    return 0

def create_final_output(name, pal, meta):
    frame_color = 'black'
    #Scaled IR Images
    resize = "-resize 200%"

    #pip
    geometrie = str(meta['OffsetX'])+str(meta['OffsetY']);
    resizepercent = 100 * int(meta['EmbeddedImageWidth'])/float(meta['Real2IR'])/int(meta['RawThermalImageWidth']);
    resize = "-resize " + str(resizepercent) + "%"
    cropx = resizepercent * int(meta['RawThermalImageWidth'])/100;
    cropy = resizepercent * int(meta['RawThermalImageHeight'])/100;

    #TODO: Update for posix
    check_call("convert "+name+"_embedded.png -gravity center -crop "+str(cropx)+"x"+str(cropy)+geometrie \
               + " -colorspace gray -sharpen 0x3 -level 30%,70%! " \
               #TODO: This is the line that gives us the MSX definition, but it's not outputting correctly (possibly due to ImageMagick Change)
               #+" ( -clone 0 -blur 0x3 ) -compose mathematics -define compose:args=0,-1,+1,0.5 -composite -colorspace gray -sharpen 0x3 -level 30%,70%! " \
               +name+"_embedded1.png", shell=True)

    #Emboss image (not sure if this produces the right style of image)
    check_call("convert "+name+"_embedded.png -gravity center -crop "+str(cropx)+"x"+str(cropy)+geometrie \
               +" -auto-level -shade 45x30 -auto-level " \
               +name+"_embedded1.png", shell=True)
    gama = float(subprocess.check_output("convert "+name+"_embedded1.png -format \"%[fx:mean]\" info:", shell=True))
    gama = math.log(gama)/math.log(0.5)
    check_call("convert "+name+"_embedded1.png -gamma " + str(gama) + " "+name+"_embedded1.png", shell=True)

    #Create PIP
    #TODO: This mostly works but the thermal blending has been an issue, but I don't think it will impact any of our current work.
    check_call("convert "+name+"_ir.png " + resize + " " + pal + " -clut "+name+"_embedded1.png +swap -compose overlay -composite "+name+"_ir2.png", shell=True)

    #Recreate Original Image Cleaned up
    # If the above worked better, this would cropped/resize the IR image to match and make one with a scale (but again, not necessary for projects)
    check_call("convert "+name+"_embedded.png "+name+"_ir2.png -gravity Center -geometry " +geometrie+ " -compose over -composite -background " + frame_color \
               + " -flatten "+name+"_final_without_scale.png", shell=True)
    check_call("convert "+name+"_final_without_scale.png -gravity Center -crop "+str(cropx)+"x"+str(cropy)+geometrie+" "+name+"_final_cropped.png", shell=True)

    return 0

def cleanup_files(name):
    #cleanup
    cm = "del"
    if os.name == "posix":
        cm = "rm"

    if os.path.isfile(str(name+'_raw.png')):
        check_call(str(cm+' '+name+'_raw.png'), shell=True)
    if os.path.isfile(str(name+'_palette.png')):
        check_call(str(cm+' '+name+'_palette.png'), shell=True)
    if os.path.isfile(str(name+'_embedded1.png')):
        check_call(str(cm+' '+name+'_embedded1.png'), shell=True)
    if os.path.isfile(str(name+'_embedded.png')):
        check_call(str(cm+' '+name+'_embedded.png'), shell=True)
    if os.path.isfile(str(name+'_ir.png')):
        check_call(str(cm+' '+name+'_ir.png'), shell=True)
    if os.path.isfile(str(name+'_ir2.png')):
        check_call(str(cm+' '+name+'_ir2.png'), shell=True)
    if os.path.isfile(str(name+'_gradient.png')):
        check_call(str(cm+' '+name+'_gradient.png'), shell=True)
        
    return 0

def process_files(relevant_path):
    included_extenstions = ['jpg', 'JPG']
    file_names = [fn for fn in os.listdir(relevant_path)
                  if any(fn.endswith(ext) for ext in included_extenstions)]
    print "file_names: " + str(file_names)

    # Gather all exif data
    exifDataAll = {}
    for file in file_names:
        imgFile = relevant_path + file
        if os.path.isfile(imgFile):
            exifDataAll[imgFile] = getExifData(imgFile) 

    # Calculate temperature range if we're normalizing
    global TEMP_RANGE
    if args.normalize:
        TEMP_RANGE = get_temperature_range(exifDataAll)

    print TEMP_RANGE

    # Calculate some metadata we'll need to extract the thermo data into an png file
    # This will create several global values and depends on the camera settings not changing between images
    calc_extract_raw_data_meta_info(exifDataAll.values()[0])

    # Used for timing the functions below
    t1t, t2t, t3t, t4t, t5t = 0, 0, 0, 0, 0

    for file in file_names:
        imgFile = relevant_path + file
        imgName = imgFile.split(relevant_path)[1].split('.')[0]
        pal = imgName + '_palette.png'
        #Process File
        if os.path.isfile(imgFile):
            print('Processing: ' + imgFile)
            exifData = exifDataAll[imgFile]

            t1s = time.time()
            create_palette_file(pal, imgFile, imgName, exifData) #6.63s, 0.42s
            t1e = time.time()
            t1t += t1e - t1s

            t2s = time.time()
            extract_raw_data(imgFile, imgName, exifData, Android) #15.39s, 1.15s
            t2e = time.time()
            t2t += t2e - t2s

            t3s = time.time()
            extract_embedded_file(imgFile, imgName, Android) #7.03s, 0.62s
            t3e = time.time()
            t3t += t3e - t3s

            t4s = time.time()
            create_final_output(imgName, pal, exifData) #17.07s, 1.27s
            t4e = time.time()
            t4t += t4e - t4s

            t5s = time.time()
            cleanup_files(imgName) #.76s, 0.05s
            t5e = time.time()
            t5t += t5e - t5s
            print "t1b:", t1e - t1s, "t2b:", t2e - t2s, "t3b:", t3e - t3s, "t4b:", t4e - t4s, "t5b:", t5e - t5s
        else:
            print('File ['+imgFile+'] Not Found!')
    
    print "t1t:", t1t, "t2t:", t2t, "t3t:", t3t, "t4t:", t4t, "t5t:", t5t

if __name__ == "__main__":
    # parse command line arguments (e.g. file path)
    parser = argparse.ArgumentParser(description='FLIR image normalizer and enhancer')
    parser.add_argument('path', default='.')
    parser.add_argument('--normalize', '-n', action='store_true')
    args = parser.parse_args()

    # Get Files In Directory
    relevant_path = args.path
    process_files(relevant_path)

