#!/bin/bash
echo " ================================== "
echo "  Verifying if the device is ready  "
echo " ================================== "
sleep 60s
source /opt/padtec/cc/cli/padtec/etc/confd/confdrc 

out="false"
while : 
do
  out=`confd_load -o -F p -p /system-controlled/ne-info/is-ready | grep -ai "is-ready" | awk -F">" '{print $2}' | awk -F"<" '{print $1}'`
#  echo ${out}
  if [ "${out}" == "true" ]; then
     echo " ================================== "
     echo "   Device is now cleaned and ready  "
     echo " ================================== "
     exit 0
  else
     echo " Retrying"
     sleep 20s
     continue
  fi
done
