import os
import argparse
import sys
import time
import glob
import pprint

from pushbullet import Pushbullet

api_key = "o.BTEXTLGP2RSiNM8huLLSAMYzSxLgBBki"


def  setParserOptions():

    parser = argparse.ArgumentParser(prog="push.py")

    parser.add_argument("-d",
                        dest="dirpath",
                        help="dirpath to scan ",
                        required=True)

    parser.add_argument("-v",
                        dest="debug",
                        action="store_true",
                        help="debug mode",
                        default=False)

    return parser


def push_image (pb,file_name,message):
    with open(file_name, "rb") as pic:
        file_data = pb.upload_file(pic, message + ": "+file_name)
        push = pb.push_file(**file_data)

def main_loop(pb,dirpath,debug):
    last_time=None

    # set the last_time
    files = filter(os.path.isfile, glob.glob(dirpath + "*.jpg"))
    for file in files:
        ft=os.path.getmtime(file)
        if last_time==None:
            last_time=ft
        if last_time<ft:
            last_time=ft

    while True:
        time.sleep(4)
        files = filter(os.path.isfile, glob.glob(dirpath + "*.jpg"))

        file_to_send=[]
        ut=0.0;
        for file in files:
            ft=os.path.getmtime(file)
            if last_time<ft:
                file_to_send +=  [file]
                ut=max(ft,ut)
        if len(file_to_send):
           print(" somthing to send :" +str(ut));
           last_time =ut
           print(file_to_send)
           if debug==0:
               for file in file_to_send:
                  push_image (pb,file,"SECURITY CAMERA")
    


def main(args=None):
    parser = setParserOptions()
    if args is None:
         opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)

    pb = Pushbullet(api_key)

    main_loop(pb,opts.dirpath,opts.debug)

    #push_image (pb,opts.input_file,"WARNING")
    #push = pb.push_note("This is the title", "This is the body")


from clarifai.rest import ClarifaiApp
      
def test1 (filename):
    app = ClarifaiApp(api_key='2fe5f07967184c0ea51f2c37eba50902')

    # get the general model
    model = app.models.get("general-v1.3")

    # predict with the model
    r=model.predict_by_filename(filename=filename);

    pprint.pprint(r);
    if (r['status']['code'] == 10000):
        c= r['outputs'][0]['data']['concepts']
        for o in c:
            if o['name'] == 'people':
                if o['value']>0.91:
                    return True
    return False





#s1 = "cam1.20181225_160000.1666634.3.jpg"
#s = 'cam1.20181225_160000.4776798.3.jpg'

#s = 'cam1.20181225_160000.1686647.3.jpg'
#s ='cam3.20181225_160000.3868494.3.jpg'
#s ='cam3.20181225_160000.5045263.3.jpg'
#s = 'cam4.20181225_160001.1776299.3.jpg'
#s = 'cam4.20181225_160001.4673277.3.jpg'
#s = 'cam4.20181225_160001.4883997.3.jpg'
#DIR='/mnt/c/BlueIris/Alerts5/'
#print(test1 (DIR+ s))


#main();


