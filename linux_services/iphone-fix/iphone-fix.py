
import argparse
import os
import sys
import subprocess
import pathlib
from PIL import Image
import piexif
import signal 

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


class NinjaBuild:
    
    def init(self):
        self.list =[]




def main(args=None):

    parser = SetParserOptions()
    if args is None:
        opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)
    convert_imgs(opts.in_dir,opts.out_dir)    

def main_video_same_path(args=None):

    parser = SetParserOptions()
    if args is None:
        opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)
    convert_video(opts.in_dir,opts.out_dir)    


def main_video_ninja(args=None):

    parser = SetParserOptions()
    if args is None:
        opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)
    convert_video_ninja(opts.in_dir,opts.out_dir)    


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
    s= 'ffmpeg -i \'{}\' -movflags use_metadata_tags -c:v libx264 -crf 24 -preset slow -c:a aac -b:a 128k \'{}\''.format(ifile,dfile)
    os.makedirs(os.path.dirname(dfile), exist_ok=True)

    print(s)
    os.system(s)


def build_cmd_convert_mov_inside(ifile,filename,dpath):
    split_tup = os.path.splitext(ifile)
    dfile =os.path.join(split_tup[0]+'.mp4')
    s= 'ffmpeg -i \'{}\' -movflags use_metadata_tags -c:v libx264 -crf 24 -preset slow -c:a aac -b:a 128k \'{}\''.format(ifile,dfile)
    print(s)
    ret=os.system(s)
    if os.WIFSIGNALED(ret):
        sig = os.WTERMSIG(ret)
        if sig == signal.SIGINT:
            exit(1)
    s= 'rm \'{}\' '.format(ifile)
    print(s)
    ret=os.system(s)
    if os.WIFSIGNALED(ret):
        sig = os.WTERMSIG(ret)
        if sig == signal.SIGINT:
            exit(1)



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

def convert_video(src_path,dst_path):

    try:
        for root, subdirs, files in os.walk(src_path):
            for file in files:
                f = os.path.join(root, file)
                process_video(f,file,dst_path)
    except KeyboardInterrupt:
        exit(1)


def process_video(ifile,filename,dst_path):
    d= {}
    if os.path.isfile(ifile):
        split_tup = os.path.splitext(filename)
        if len(split_tup) == 2:
            ex = split_tup[1][1:].lower()

            if ex == 'heic':
                #build_cmd_convert_jpg(ifile,filename,dst_path)
                pass
            elif ex == 'mov':
                build_cmd_convert_mov_inside(ifile,filename,dst_path)
            elif ex == 'avi':
                build_cmd_convert_mov_inside(ifile,filename,dst_path)



def process_video_ninja(ifile,filename,dst_path):
    d= {}
    if os.path.isfile(ifile):
        split_tup = os.path.splitext(filename)
        if len(split_tup) == 2:
            ex = split_tup[1][1:].lower()

            if ex == 'heic':
                #build_cmd_convert_jpg(ifile,filename,dst_path)
                pass
            elif ex == 'mov':
                build_cmd_convert_mov_inside(ifile,filename,dst_path)
            elif ex == 'avi':
                build_cmd_convert_mov_inside(ifile,filename,dst_path)


def convert_video_ninja(src_path,dst_path):

    try:
        for root, subdirs, files in os.walk(src_path):
            for file in files:
                f = os.path.join(root, file)
                process_video_ninja(f,file,dst_path)
    except KeyboardInterrupt:
        exit(1)


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

def ninja_escape(path):
    return path.replace(' ', '$ ')

class NinjaBuild:
    
    def __init__(self):
        self.of =[] # files list (origin)
        self.d = {} # map of file name
        self.heic =[] # files list (origin)

    def add_dir(self,dir):
        for root, subdirs, files in os.walk(dir):
            for file in files:
                f = os.path.join(root, file)
                if os.path.isfile(f):
                    split_tup = os.path.splitext(file)
                    if len(split_tup) == 2:
                        ex = split_tup[1][1:].lower()

                        if ex == 'heic':
                            self.add_pic(f)
                        elif ex == 'mov':
                            self.add(f)
                        elif ex == 'avi':
                            self.add(f)
                        elif ex == 'mts':
                            self.add(f)

    def add(self, file):
        if not (file in self.d):
            self.of.append(file)
            self.d[file] = True

    def add_pic(self, file):
        if not (file in self.d):
            self.heic.append(file)
            self.d[file] = True

    def get_file_con(self):
           s= '''

rule cv
  command = ffmpeg -hide_banner -loglevel error  -i $in -movflags use_metadata_tags -c:v libx264 -crf 24 -preset slow -c:a aac -b:a 128k -y $out
  description = Converting $in to $out

rule heif
  command = heif-convert -q 100  $in $out
  description = Converting heif $in to $out

'''
           for o in self.of:
               split_tup = os.path.splitext(o)
               dfile =os.path.join(split_tup[0]+'.mp4')

               s += 'build {} : cv {} \n'.format(ninja_escape(dfile),ninja_escape(o))

           for o in self.heic:
               split_tup = os.path.splitext(o)
               dfile =os.path.join(split_tup[0]+'.jpg')

               s += 'build {} : heif {} \n'.format(ninja_escape(dfile),ninja_escape(o))

           return s
    
    def write_file(self,file_name) :
        with open(file_name, "w") as f:
            f.write(self.get_file_con())



# make sure the path exist before the copy 
if __name__ == '__main__':
    n = NinjaBuild()
    n.add_dir('/mnt/nfs2/')
    n.write_file('build.ninja')

    #main_video_same_path()





