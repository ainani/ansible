#!/bin/bash

PNMS_PROPERTIES_FILE=installPNMS.properties
MEDIATOR_PROPERTIES_FILE=installMediator.properties
DOMAIN_MANAGER_PROPERTIES_FILE=installDomainManager.properties
DUNIT_PROPERTIES_FILE=distanceUnit.properties

echo "- Reading parameters from properties files"
PEER_SQL_SERVER=`awk -F"=" '/PEER_SQL_SERVER/ { print $2 }' ${PNMS_PROPERTIES_FILE}`
SERVER_ID=`awk -F"=" '/SERVER_ID/ { print $2 }' ${PNMS_PROPERTIES_FILE}`
PNMS_IP=`awk -F"=" '/PNMS_IP/ { print $2 }' ${PNMS_PROPERTIES_FILE}`
INSTALL_PNMS_DIR=`awk -F"=" '/INSTALL_PNMS_DIR/ { print $2 }' ${PNMS_PROPERTIES_FILE}`
PEER_NCS_IP=`awk -F"=" '/PEER_SQL_SERVER/ { print $2 }' ${DOMAIN_MANAGER_PROPERTIES_FILE}`
NCS_IP=`awk -F"=" '/NCS_IP/ { print $2 }' ${DOMAIN_MANAGER_PROPERTIES_FILE}`
INSTALL_TOPOLOGY=`awk -F"=" '/INSTALL_TOPOLOGY/ { print $2 }' ${PNMS_PROPERTIES_FILE}`
ON_SAME_MACHINE_NCS=`awk -F"=" '/ON_SAME_MACHINE/ { print $2 }' ${DOMAIN_MANAGER_PROPERTIES_FILE}`
MEDIATOR_ON_THIS_MACHINE=`awk -F"=" '/MEDIATOR_ON_THIS_MACHINE/ { print $2 }' ${MEDIATOR_PROPERTIES_FILE}`
PNMS_VERSION=`echo $INSTALL_PNMS_DIR | awk -F"/" {'print $4'} | awk -F"_V" {'print $2'}`



##########Configuring database############


##
# Start PNMS along with Topology
PNMS_PID=`ps -eaf | grep appserver | grep -v grep | awk '{print $2}' | wc -l`
echo PNMS_ID: $PNMS_PID
if [[ -d "../pnmsinstall" ]]
then

if [ "$INSTALL_TOPOLOGY" = "true" ]
then

	cd ../pnmsinstall/pnms/bin
	./runpnms.sh stop
	sleep 5
	./runpnms.sh start with-nodemanager-topology ${PNMS_VERSION}
	sleep 5	
	cd -
else
	echo " - Topology is not set to be installed on same machine"
	cd ../pnmsinstall/pnms/bin
	./runpnms.sh stop
	sleep 5
	./runpnms.sh start with-nodemanager ${PNMS_VERSION}
	sleep 5	
	cd -
fi
elif [[ ! -d "../pnmsinstall" ]]
then
	echo "------ PNMS is not installed on this server ------"
else
	echo "PNMS is already running... Skipping starting PNMS/Topology"
fi
