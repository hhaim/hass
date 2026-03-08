
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

    parser.add_argument("--sync-hyperdx",
                        dest="sync_hyperdx",
                        help="sync hyperdx ",
                        action="store_true",
                        default=False)

    # the collector in hass docker 
    parser.add_argument("--sync-vector_hass",
                        dest="sync_vector_hass",
                        help="sync vector_hass ",
                        action="store_true",
                        default=False)

    parser.add_argument("--sync-fri",
                        dest="sync_frigate",
                        help="sync frigate ",
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

#
def get_sync_hass():
    cmd ='rsync -avz --exclude=".git" --exclude="netdc"  --exclude="store/zigbee2mqtt_01" --exclude="store/zigbee2mqtt_02" --exclude="cfg/hass/known_devices.yaml" --exclude="linux_services"  --exclude="services" . {}:{} '.format(RH,REMOTE_HASS)
    return cmd

# backup z2m data 
def get_backup_z2m():
    cmd ='rsync -avz   --exclude="*backup*" --exclude="*.log"  {}:{} store '.format(RH,REMOTE_HASS_STORE+'zigbee2mqtt_01',)
    print(cmd)
    return cmd

def get_backup_z2m_base():
    cmd ='rsync -avz   --exclude="*backup*" --exclude="*.log"  {}:{} store '.format(RH,REMOTE_HASS_STORE+'zigbee2mqtt_02',)
    print(cmd)
    return cmd


def get_sync_net():
    cmd ='rsync -avz  netdc/ {}:{} '.format(RH,REMOTE_NETDC)
    return cmd

def get_sync_frigate():
    cmd ='rsync -avz  frigate/ {}:{} '.format('frigate','frigate')
    return cmd

def get_dump_hyperdx():
    cmd ='rsync -avz  hyperdx/ {}:{} '.format('photop','/home/hhaim/hyperdx/')
    return cmd

def get_dump_vector_hass():
    cmd ='rsync -avz  vector_dev_hass/ {}:{} '.format(RH,REMOTE_HASS+"vector_dev_hass/")
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
    
    if opts.sync_hyperdx:
        run_cmd(get_dump_hyperdx())

    if opts.sync_vector_hass:
        run_cmd(get_dump_vector_hass())

    if opts.ddns:
        run_cmd(get_dump_dm())
    if opts.dmq:
        run_cmd(get_dump_mq())

    if opts.sync_hass:
        run_cmd(get_sync_hass())
        run_cmd(get_backup_z2m())
        run_cmd(get_backup_z2m_base())
        

    if opts.sync_net:
        run_cmd(get_sync_net())

    if opts.sync_frigate:
        run_cmd(get_sync_frigate())

    

if __name__ == '__main__':
    main()
    