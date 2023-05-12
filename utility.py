
import argparse
import os
import sys
import subprocess

#--d-dnsmasq
#--d-mq 
#+--sync-hass
#
#--sync-all
#--sync-cc

def SetParserOptions():
    parser = argparse.ArgumentParser(prog="utility.py")

    parser.add_argument("--sync-hass",
                        dest="sync_hass",
                        help="sync hass info",
                        action="store_true",
                        default=False)

    parser.add_argument("--sync-net",
                        dest="sync_net",
                        help="sync ad ",
                        action="store_true",
                        default=False)

    parser.add_argument("--d-dnsmasq",
                        dest="ddns",
                        help="dump dns_masq ",
                        action="store_true",
                        default=False)

    parser.add_argument("--d-mq ",
                        dest="dmq",
                        help="dump mosquito log ",
                        action="store_true",
                        default=False)

    return parser

RH = os.getenv('REMOTE_HASS') 
if RH == None:
    print(" you must define remote addr of hass as raw ip")
    exit(-1)

REMOTE_PATH = '/home/hhaim/'
REMOTE_NETDC_STORE = REMOTE_PATH+'hass/netdc/store/'
REMOTE_HASS_STORE = REMOTE_PATH+'hass/store/'
REMOTE_HASS = REMOTE_PATH+'hass/'
REMOTE_NETDC =REMOTE_HASS+"netdc/"


def get_ssh_cmd():
    cmd ='ssh {} '.format(RH)
    return cmd

def get_rsync_cmd():
    cmd ='rsync -avz . - '.format(RH)
    return cmd

def get_r_cmd(cmd):
    return "'" + cmd + "'"

def get_dump_dm():
    cmd=get_ssh_cmd()+get_r_cmd('cat '+REMOTE_NETDC_STORE+'dnsmasq/dnsmasq.leases')
    return cmd

def get_dump_mq():
    cmd=get_ssh_cmd()+get_r_cmd('cat '+REMOTE_HASS_STORE+'mosquitto/log/mosquitto.log')
    return cmd

def get_sync_hass():
    cmd ='rsync -avz --exclude=".git" --exclude="netdc" --exclude="cfg/hass/known_devices.yaml" --exclude="linux_services"  --exclude="services" . {}:{} '.format(RH,REMOTE_HASS)
    return cmd

def get_sync_net():
    cmd ='rsync -avz  netdc/ {}:{} '.format(RH,REMOTE_NETDC)
    return cmd

def run_cmd(cmd):    
   print('run :'+cmd) 
   os.system(cmd)

def main(args=None):

    parser = SetParserOptions()
    if args is None:
        opts = parser.parse_args()
    else:
        opts = parser.parse_args(args)
    
    if opts.ddns:
        run_cmd(get_dump_dm())
    if opts.dmq:
        run_cmd(get_dump_mq())

    if opts.sync_hass:
        run_cmd(get_sync_hass())
    if opts.sync_net:
        run_cmd(get_sync_net())

    

if __name__ == '__main__':
    main()        