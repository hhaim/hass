#!/bin/sh 
# copy this file to secure location and add it to dhcp-script=/usr/local/dap/etc/dnsmasq/mqttpub.sh


op="${1:-op}"
mac="${2:-mac}"
ip="${3:-ip}"
hostname="${4}"

tstamp="`date '+%Y-%m-%d %H:%M:%S'`"

topic="network/dhcp/${mac}"
payload="{ \"op\":\"${op}\", \"ip\":\"${ip}\", \"tstamp\":\"${tstamp}\", \"host\":\"${hostname}\"}"

mosquitto_pub -u [mqtt_user] -P [mqtt_pwd]  -t "${topic}" -m "${payload}"



