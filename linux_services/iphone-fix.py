
import argparse
import os
import sys
import subprocess
import pathlib


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

    

def build_cmd_convert_jpg(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    dfile =os.path.join(dpath,split_tup[0]+'.jpg')
    s= 'heif-convert -q 100 {} {}'.format(ifile,dfile)
    print(s)
    os.system(s)

def build_cmd_convert_mov(ifile,filename,dpath):
    split_tup = os.path.splitext(filename)
    dfile =os.path.join(dpath,split_tup[0]+'.mp4')
    s= 'ffmpeg -i {} -movflags use_metadata_tags -c:v libx264 -crf 24 -preset slow -c:a aac -b:a 128k {}'.format(ifile,dfile)
    print(s)
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
    

def convert_imgs(src_path,dst_path):

    for root, subdirs, files in os.walk(src_path):
        for file in files:
            f = os.path.join(root, file)
            process(f,file,dst_path)
            

if __name__ == '__main__':
    main()

