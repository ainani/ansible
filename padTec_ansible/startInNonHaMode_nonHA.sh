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
PNMS_PID=`ps -eaf | grep java | grep appserver | grep -v grep | awk '{print $2}'`
echo PNMS_ID: $PNMS_PID
if [[ -d "../pnmsinstall" ]] && [[ $PNMS_PID == "" ]]
then

DIR_PATH="$(echo "${INSTALL_PNMS_DIR}" | sed 's#/#\\/#g')"
sed -i "/jboss.home.dir=/ s/=.*/=${DIR_PATH}\/pnms\/appserver-wildfly/" ../pnmsinstall/pnms/etc/runnodemanager.properties
sed -i 's/appserver.ip=127.0.0.1/appserver.ip='${PNMS_IP}'/g' ../pnmsinstall/pnms/etc/runnodemanager.properties


if [ "$INSTALL_TOPOLOGY" = "true" ]
then
echo "------------ Start Topology/PNMS -----------"
        echo " - Topology is set to be installed on same machine"
        DIR_PATH="$(echo "${INSTALL_PNMS_DIR}" | sed 's#/#\\/#g')"
        echo "PATH = "$DIR_PATH
        sed -i "/jboss.home.dir=/ s/=.*/=${DIR_PATH}\/pnms\/appserver-wildfly/" ../pnmsinstall/pnms/etc/runtopology.properties
        sed -i 's/appserver.ip=127.0.0.1/appserver.ip='${PNMS_IP}'/g' ../pnmsinstall/pnms/etc/runtopology.properties
        mysql -uroot -ppadtec << EOF
        INSERT INTO pnmsdb.configuration (name, value, cluster_id) VALUES ('topology-address', '${PNMS_IP}',${SERVER_ID}), ('topology-context', '/networktopology',${SERVER_ID}), ('topology-rest-path', '/rest',${SERVER_ID}), ('topology-port', '8080',${SERVER_ID}), ('topology-secret-key', '6d10ca529f1e803e6c86b4398315fda5b843095d24d8572d81b2249f7ad01ddd',${SERVER_ID}), ('pnms-address', '${PNMS_IP}',${SERVER_ID});

EOF

        mysql -uroot -ppadtec << EOF
        UPDATE pnmstopologydb.topology_config SET value='${PNMS_IP}' WHERE name='pnms-address' and cluster_id=${SERVER_ID};
EOF

        cd ../pnmsinstall/pnms/bin
        ./runpnms.sh start with-nodemanager-topology ${PNMS_VERSION}
        cd -
else
        echo " - Topology is not set to be installed on same machine"
        cd ../pnmsinstall/pnms/bin
        ./runpnms.sh start with-nodemanager ${PNMS_VERSION}
        cd -
fi
elif [[ ! -d "../pnmsinstall" ]]
then
        echo "------ PNMS is not installed on this server ------"
else
        echo "PNMS is already running... Skipping starting PNMS/Topology"
fi
sleep 5

###############################################
# Start Mediator
MED_PID=`ps -eaf | grep java | grep mediator | grep -v grep | awk '{print $2}'`
echo MED_PID: $MED_PID
if [[ -d "../medinstall" ]] && [[ $MED_PID == "" ]]
then
        echo "------------ Start Mediator ----------------"
        echo " - Starting Mediator"
        cd ../medinstall/mediator/bin/
        ./runmediator.sh start
        cd -
elif [[ ! -d "../medinstall" ]]
then
        echo "------- Mediator is not installed on this server --------"
else
        echo "Mediator process is already running.... Skipping starting Mediator"
fi
sleep 5

#################################################
# Start DomainManager
NCS_PID=`ps -eaf | grep java | grep ncs | grep -v grep | awk '{print $2}'`
echo NCS_PID: $NCS_PID
if [[ -d "../dminstall" ]] && [[ $NCS_PID == "" ]]
then
        echo "------------ Starting Domain Manager ----------------"

        cd ../dminstall/domainmanager/bin
        cd -
        ./updateNotificationPointer.sh
        sleep 5

        cd ../dminstall/domainmanager/gotns/
        source ~/.ncs_env
        echo 1 | gotns start
        cd -
        sleep 5
elif [[ ! -d "../dminstall" ]]
then
        echo "----------- Domain Manager is not installed on this server ------------"
else
        echo "Domain Manager process already running..... Skipping starting Domain Manager"
fi
echo "Execution of startInNonHaMode.sh script completed!"
sleep 5

echo "------------ POST Installation Checkup ------------"
PNMS_PID=`ps -eaf | grep java | grep appserver | grep -v grep | awk '{print $2}'`
echo PNMS_ID: $PNMS_PID

MED_PID=`ps -eaf | grep java | grep mediator | grep -v grep | awk '{print $2}'`
echo MED_PID: $MED_PID

NCS_PID=`ps -eaf | grep java | grep ncs | grep -v grep | awk '{print $2}'`
echo NCS_PID: $NCS_PID

exit 0

