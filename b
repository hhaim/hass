#! /bin/bash

if [ -z "$REMOTE_HASS" ]
then
      echo "\$REMOTE_HASS should be set to the remote hass ip"
      exit -1
fi      

python3 utility.py $@


