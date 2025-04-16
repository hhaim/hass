
import argparse
import os
import sys
import subprocess
import pathlib
from PIL import Image
import piexif


def SetParserOptions():
    parser = argparse.ArgumentParser(prog="utility.py")

    parser.add_argument("--in-dir",
                        dest="in_dir",
                        help="",
                        type = pathlib.Path
                        )

    parser.add_argument("--out-dir",
                        dest="out_dir",
                        help="out dir ",
                        type=pathlib.Path
                        )



    return parser



def main(args=None):

    parser = SetParserOptions()
    if args is None:
        opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)
    convert_imgs(opts.in_dir,opts.out_dir)    


def build_cmd_orf_jpg(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    dfile =os.path.join(dpath,split_tup[0]+'.jpg')
    s= 'darktable-cli {} {}'.format(ifile,dfile)
    print(s)
    os.system(s)




def build_cmd_convert_jpg(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    b =os.path.basename(os.path.dirname(ifile))
    dfile =os.path.join(dpath,b,split_tup[0]+'.jpg')
    s= 'heif-convert -q 100 {} {}'.format(ifile,dfile)
    os.makedirs(os.path.dirname(dfile), exist_ok=True)
    print(s)
    os.system(s)

def build_cmd_convert_mov(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    b =os.path.basename(os.path.dirname(ifile))
    dfile =os.path.join(dpath,b,split_tup[0]+'.mp4')
    s= 'ffmpeg -i {} -movflags use_metadata_tags -c:v libx264 -crf 24 -preset slow -c:a aac -b:a 128k {}'.format(ifile,dfile)
    os.makedirs(os.path.dirname(dfile), exist_ok=True)

    print(s)
    os.system(s)

def build_cmd_cp_jpg(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    b =os.path.basename(os.path.dirname(ifile))
    dfile =os.path.join(dpath,b,split_tup[0]+'.jpg')
    s= 'cp {} {}'.format(ifile,dfile)
    print(s)
    os.makedirs(os.path.dirname(dfile), exist_ok=True)
    os.system(s)

def process(ifile,filename,dst_path):
    d= {}
    if os.path.isfile(ifile):
        split_tup = os.path.splitext(filename)
        if len(split_tup) == 2:
            ex = split_tup[1][1:]

            if ex == 'HEIC':
                build_cmd_convert_jpg(ifile,filename,dst_path)
            elif ex == 'MOV':
                build_cmd_convert_mov(ifile,filename,dst_path)
            elif ex == 'JPG':
                if is_iphone_origin(ifile):
                    build_cmd_cp_jpg(ifile,filename,dst_path)
    

def convert_imgs(src_path,dst_path):

    for root, subdirs, files in os.walk(src_path):
        for file in files:
            f = os.path.join(root, file)
            process(f,file,dst_path)




def is_iphone_origin(image_path):
        m = extract_jpg_metadata(image_path)
        if len(m)>0:
            if 'Camera' in m:
                if m['Camera'] == 'Apple iPhone 14 Plus':
                    if m['size']>1000000:
                        return True
        return False             


def extract_jpg_metadata(image_path):
    img = Image.open(image_path)
    metadata = {}
    metadata["size"]=os.path.getsize(image_path)
    try: 
       exif_data = piexif.load(img.info.get('exif', b''))
    except:
       return metadata
        
    #print(exif_data)

    # Basic metadata

    # Extract camera make and model
    make = exif_data["0th"].get(piexif.ImageIFD.Make, b"").decode(errors="ignore")
    model = exif_data["0th"].get(piexif.ImageIFD.Model, b"").decode(errors="ignore")
    metadata["Camera"] = f"{make} {model}".strip()

    # Extract capture time
    datetime = exif_data["0th"].get(piexif.ImageIFD.DateTime, b"").decode(errors="ignore")
    metadata["DateTime"] = datetime
    return metadata

    # GPS data if available
    gps_data = exif_data.get("GPS", {})
    if gps_data:
        def convert_to_degrees(value):
            d, m, s = value
            return d[0]/d[1] + m[0]/m[1]/60 + s[0]/s[1]/3600

        lat = convert_to_degrees(gps_data[piexif.GPSIFD.GPSLatitude])
        if gps_data[piexif.GPSIFD.GPSLatitudeRef] == b'S':
            lat = -lat

        lon = convert_to_degrees(gps_data[piexif.GPSIFD.GPSLongitude])
        if gps_data[piexif.GPSIFD.GPSLongitudeRef] == b'W':
            lon = -lon

        metadata["GPS"] = (lat, lon)

    return metadata

# make sure the path exist before the copy 
if __name__ == '__main__':
    main()


