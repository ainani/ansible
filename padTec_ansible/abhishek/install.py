#!/usr/bin/python
# -*- coding: utf-8 -*-

import ConfigParser         # Used for parsing the config.txt file
import subprocess           # Used for few shell script execution locally 
import os                   # Used for execution of shell scripts locally
import paramiko             # Used for password less SSH connections of servers
import collections          # Used for ordered dictionary
import tarfile              # Used for tar and untar build
import requests             # Used for verification of GUI access post installation
import time                 # Used for system-time
import sys                  # Used for exit method
import threading            # Used for parallel execution on multiple nodes
import datetime             # used for system-time
import shutil               # Used for high level file opetations like copy and remove files
import glob                 # Used for Unix style pathname pattern expansion
import logging              # Used for logging the script flow in python
from IPy import IP	    # Used for validation of IP addresses

global ncs_ip_1, med_ip_1, nms_ip_1, topology_ip_1, virtual_ip_nms_1, \
    virtual_ip_ncs_1, virtual_ip_topology_1, ncs_ip_2, med_ip_2, nms_ip_2, topology_ip_2, virtual_ip_nms_2, \
    virtual_ip_ncs_2, virtual_ip_topology_2, local_cluster1, local_cluster2, unique_ips, ssh



def getTimeStamp(timestamp=''):
    if str(timestamp) == '':
        timestamp = time.time()
    ts = \
        datetime.datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y_%H:%M:%S'
            )
    return '\n[' + str(ts) + ']'


def parser(config_file):
    config = ConfigParser.ConfigParser()
    config.optionxform = str
    try:
        config.read(config_file)
    except ConfigParser.MissingSectionHeaderError as error:
        print  error
    return config


def readSectionFromFlatfile(config, sectionName):
    print '\t - Reading ' + sectionName + ' section'
    if config.has_section(sectionName):
        return config.items(sectionName)
    else:
        print "\t [" + sectionName + "] section not found in config file"
        exit()

def readOptions(config, sectionName, option):
    optional = ['uninstallPath', 'topology_ip_1', 'topology_ip_2']
    if config.has_option(sectionName, option):
        print "\t - Found '" + option + "' in '" + sectionName + "'"
        return config.get(sectionName, option)
    else:
        if option in optional:
            print "\t - Optional option '" + option + "' under section '" + sectionName + "' is missing"
            return False
        else:
            print "\t - Mandatory option '" + option + "' under section '" + sectionName + "' is missing"
            exit()

def raw_ssh(ip):
    sshObj = paramiko.SSHClient()
    sshObj.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    sshObj.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshObj.connect(hostname=ip, username='padtec', password='abcd1234!')
    return sshObj


def line_buffered(f):
    line_buf = ''
    start_time = time.time()
    while not f.channel.exit_status_ready():
        time_elapsed = time.time() - start_time
        if int(time_elapsed) > 30:
            print '\t\t Exiting after ' + str(time_elapsed)
            break
        line_buf += f.read(1)
        if line_buf.endswith('\n'):
            yield line_buf
            line_buf = ''
            start_time = time.time()

def ssh_command_noBuffer(ssh, cmd):
    (stdin, stdout, stderr) = ssh.exec_command(cmd)
    print '\t' + stdout.read()
    stdout.flush()

def ssh_command_new(ssh,cmd):
    (stdin, stdout, stderr) = ssh.exec_command(cmd)
    timeout = 30
    endtime = time.time() + timeout
    while not stdout.channel.eof_received:
        time.sleep(1)
        if time.time() > endtime:
            stdout.channel.close()
            break
    stdout.read()


def ssh_command(ssh, cmd, printOutput=0):
    (stdin, stdout, stderr) = ssh.exec_command(cmd)
    stdin.flush()
#       print "\t - Operations on remote shell : ", ip

    if printOutput == 1:
        return stdout.read()
    elif printOutput == 2:
        for l in line_buffered(stdout):
            print '\t' + l.strip()
    else:
        pass
        
#               print "\n---ERR-Start---\n\t" + stderr.read() + "\n---ERR-End---\n"

    print '\t' + stdout.read()
    stdout.flush()


def pullBuild(ssh, src, dst):
    print '\t  - Pulling Build.....'
    transfer = ssh.open_sftp()
    transfer.get(src, dst)
    transfer.close()
    return dst


def pushBuild(ssh, src, dst):

#    ssh = raw_ssh(ip)
#    transfer = ssh.open_sftp()

    transfer = ssh.open_sftp()
    try:
        transfer.chdir(installDir)  # Test if remote_path exists
    except IOError:
        transfer.mkdir(installDir)  # Create remote_path
        transfer.chdir(installDir)
    transfer.put(src, dst)
    transfer.close()


#    ssh.close()

def untarBuildLocally():
    print '\n' + getTimeStamp() + ' Untar Build Locally InProgress'
    tf = tarfile.open(localBuildPath)
    files = tf.getnames()
    tf.extractall(installDir)
    print ' \t - Untar done at : ', installDir + '/' + files[0]
    parentUntarDir = files[0]
    return parentUntarDir


def ssh_key_exchange(
    hostname,
    username='padtec',
    password='abcd1234!',
    key='',
    ):
    global ssh

            # Checking current hostname exists or not in file

    chck_ssh_cmd = 'cat ~/.ssh/known_hosts | grep ' + hostname \
        + ' | cut -d \' \' -f 1'
    out = subprocess.check_output([chck_ssh_cmd], shell=True).rstrip()

    print ' \t - Setting up passwordless communication to: ', hostname

    if out == hostname:
        print '\t\t - Keys already present for ', hostname, \
            ' skipping process...'
        try:
            ssh.update({hostname: raw_ssh(hostname)})

#                       ssh[hostname].close()

            return
        except Exception, e:
            print '\t\t - Connection Failed'
            print e
    else:
        print '\t\t - Keys not present for ', hostname, \
            ' initiating process...'
        try:
            ssh.update({hostname: raw_ssh(hostname)})
            ssh[hostname].exec_command('mkdir -p ~/.ssh/')
            ssh[hostname].exec_command('echo "%s" >> ~/.ssh/authorized_keys'
                     % key)
            ssh[hostname].exec_command('chmod 644 ~/.ssh/authorized_keys'
                    )
            ssh[hostname].exec_command('chmod 700 ~/.ssh/')

#                       ssh[hostname].close()

            return
        except Exception, e:
            print '\t\t - Connection Failed'
            print e


def copyBuildRemotely():
    print '\n' + getTimeStamp() + ' Copying Build to remote servers'
    threadCopyBuild = {}
    for ip in unique_ips:
            print '\t - Pushing the build to : ' + ip
            sshObj = ssh[ip]
            threadCopyBuild[ip] = threading.Thread(target=pushBuild,
                    args=(sshObj, localBuildPath, localBuildPath))
            threadCopyBuild[ip].start()

    for ip in unique_ips:
            threadCopyBuild[ip].join()
            print '\t - Push File completed at :', localBuildPath, '\n'


def untarBuildRemotely():
    threadUntarBuildRemotely = {}
    for ip in unique_ips:
            print '\n' + getTimeStamp() \
                + ' Untar build remotely at ip: ', ip
            cmd = 'tar -xzf ' + localBuildPath + ' -C ' + installDir
            threadUntarBuildRemotely[ip] = \
                threading.Thread(target=ssh_command, args=(ssh[ip],
                                 cmd))
            threadUntarBuildRemotely[ip].start()
    for ip in unique_ips:
            threadUntarBuildRemotely[ip].join()
            print '\t - Untar build completed remotely at : ', ip \
                + ' - ' + installDir + '/' + parentUntarBuildPath


def pullBuildFromBuildServer():

        # Will check if directory exists or not and create accordingly if doest not exists

    if not os.path.exists(installDir):
        os.makedirs(installDir)
        print ' - Directory (', installDir, ') Created '
    else:
        print ' - Directory (', installDir, ') already exists'

        # Will sftp the build from buildServer and given path

    print '\n' + getTimeStamp() + ' Pulling build (', \
        buildServerBuildPath, ') from build server (', buildServerIP, \
        ')'
    remotepath = buildServerBuildPath
    localpath = installDir + '/' + buildName

#       sshObj=raw_ssh(buildServerIP)

        # Pulling build from buildserver

    dst = pullBuild(ssh[buildServerIP], remotepath, localpath)
    print '\t  - Transfer completed at: ', dst


def changePropFiles():
    print '\n' + getTimeStamp() \
        + ' Updating properties files as per setup details'
    propDir = untarFileDir + '/bin/'
    ON_SAME_MACHINE = checkProcessLoc()
    MEDIATOR_ON_THIS_MACHINE = checkProcessLoc(ncsCheck=0)
    NCS_ON_THIS_MACHINE = checkProcessLoc(medCheck=0)
    SERVER_ID = '1'
    SERVER_ID_CLUSTER_1 = '1'
    SERVER_ID_CLUSTER_2 = '2'
    NCS_HA_MODE_CLUSTER_1 = 'n1'
    NCS_HA_MODE_CLUSTER_2 = 'n2'
    gotns_file = untarFileDir+'/pkg/domainmanager/lib/gotns*.tar.gz'
    if topology_ip_1 == nms_ip_1:
        TOPOLOGY='true'
    else:
        TOPOLOGY='false'
    

    for f in glob.glob(gotns_file):
        gotns_file_name = f.split('/')[-1]
    
    if int(isHA) == 0:
        
        cmdNonHAList = []

                # ### DomainManager.properties

        cmdNonHAList.append('sed -i "s~INSTALL_DOMAINMANAGER_DIR=.*~INSTALL_DOMAINMANAGER_DIR=' \
            + untarFileDir + '/dminstall~" ' + propDir \
            + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + propDir \
            + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~NCS_BINARY_FILE_PATH=.*~NCS_BINARY_FILE_PATH=' \
            + untarFileDir + '/pkg/domainmanager/lib~" ' + propDir \
            + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~NCS_BINARY_INSTALL_PATH=.*~NCS_BINARY_INSTALL_PATH=' \
            + untarFileDir + '/ncs~" ' + propDir \
            + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~HOST_IP_ADDRESS=.*~HOST_IP_ADDRESS=' \
            + ncs_ip_1 + '~" ' + propDir \
            + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~NCS_IP=.*~NCS_IP=' + ncs_ip_1 + '~" ' \
            + propDir + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~NODEMANAGER_IP=.*~NODEMANAGER_IP=' + nms_ip_1 \
            + '~" ' + propDir + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' + SERVER_ID + '~" ' \
            + propDir + '/installDomainManager.properties')
        cmdNonHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + NCS_ON_THIS_MACHINE + '~" ' + propDir \
            + '/installDomainManager.properties')


                # ### Mediator.properties

        cmdNonHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + propDir \
            + '/installMediator.properties')
        cmdNonHAList.append('sed -i "s~PNMS_IP_ADDRESS=.*~PNMS_IP_ADDRESS=' \
            + nms_ip_1 + '~" ' + propDir + '/installMediator.properties')
        cmdNonHAList.append('sed -i "s~MEDIATOR_IP_ADDRESS=.*~MEDIATOR_IP_ADDRESS=' \
            + med_ip_1 + '~" ' + propDir + '/installMediator.properties')
        cmdNonHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + propDir \
            + '/installMediator.properties')

                # ### PNMS.properties

        cmdNonHAList.append('sed -i "s~INSTALL_PADNMS_DIR=.*~INSTALL_PADNMS_DIR=' \
            + untarFileDir + '/etc~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~INSTALL_PNMS_DIR=.*~INSTALL_PNMS_DIR=' \
            + untarFileDir + '/pnmsinstall~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_1 + '~" ' \
            + propDir + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' + SERVER_ID + '~" ' \
            + propDir + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + ON_SAME_MACHINE + '~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~MEDIATOR_ON_THIS_MACHINE=.*~MEDIATOR_ON_THIS_MACHINE=' \
            + MEDIATOR_ON_THIS_MACHINE + '~" ' + propDir \
            + '/installPNMS.properties')
        cmdNonHAList.append('sed -i "s~INSTALL_NODEMANAGER_DIR=.*~INSTALL_NODEMANAGER_DIR=' \
            + untarFileDir + '/installnodemanager~" ' + propDir \
            + '/installNodeManager.properties')
        cmdNonHAList.append('sed -i "s~INSTALL_TOPOLOGY=.*~INSTALL_TOPOLOGY=' + TOPOLOGY + '~" ' + propDir + '/installPNMS.properties')

                # ### Topology.properties

        if topology_ip_1 != 'False':
            cmdNonHAList.append('sed -i "s~INSTALL_TOPOLOGY_DIR=.*~INSTALL_TOPOLOGY_DIR=' \
                + untarFileDir + '/topologyinstall~" ' + propDir \
                + '/installTopology.properties')
            cmdNonHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_1 + '~" ' \
                + propDir + '/installTopology.properties')
            cmdNonHAList.append('sed -i "s~TOPOLOGY_IP=.*~TOPOLOGY_IP=' + topology_ip_1 \
                + '~" ' + propDir + '/installTopology.properties')

        for cmd in cmdNonHAList:
            os.system(cmd)
    
    
    ### HA Mode changes start from here
    elif int(isHA) == 1:
    	eth_nms_ip_1_cmd='ip addr show | grep -i ' + nms_ip_1
    	eth_nms_ip_2_cmd='ip addr show | grep -i ' + nms_ip_2
    	eth_ncs_ip_1_cmd='ip addr show | grep -i ' + ncs_ip_1
    	eth_ncs_ip_2_cmd='ip addr show | grep -i ' + ncs_ip_2
    
    	eth_nms_ip1=ssh_command(ssh[nms_ip_1], eth_nms_ip_1_cmd, 1).split(' ')[-1].rstrip()
    	eth_nms_ip2=ssh_command(ssh[nms_ip_2], eth_nms_ip_2_cmd, 1).split(' ')[-1].rstrip()
    	eth_ncs_ip1=ssh_command(ssh[ncs_ip_1], eth_ncs_ip_1_cmd, 1).split(' ')[-1].rstrip()
    	eth_ncs_ip2=ssh_command(ssh[ncs_ip_2], eth_ncs_ip_2_cmd, 1).split(' ')[-1].rstrip()
    	

	if topology_ip_2 == nms_ip_2:
            TOPOLOGY='true'
    	else:
            TOPOLOGY='false'
        
	ON_SAME_MACHINE = checkProcessLoc_c2()
        MEDIATOR_ON_THIS_MACHINE = checkProcessLoc_c2(ncsCheck=0)
        NCS_ON_THIS_MACHINE = checkProcessLoc_c2(medCheck=0)

                # Changes for cluster1

        global local_cluster1
        local_cluster1 = installDir + '/cluster_1'
        if not os.path.exists(local_cluster1):
            os.makedirs(local_cluster1)
            print ' - Directory (', local_cluster1, ') Created '
        else:
            print ' - Directory (', local_cluster1, ') already exists'

        for file_1 in glob.glob(propDir + '*.properties'):
            shutil.copy2(file_1, local_cluster1)

                # ## DomainManager.properties
        cmdHAList = []

        cmdHAList.append('sed -i "s~INSTALL_DOMAINMANAGER_DIR=.*~INSTALL_DOMAINMANAGER_DIR=' \
            + untarFileDir + '/dminstall~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_BINARY_FILE_PATH=.*~NCS_BINARY_FILE_PATH=' \
            + untarFileDir + '/pkg/domainmanager/lib~" ' \
            + local_cluster1 + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_BINARY_INSTALL_PATH=.*~NCS_BINARY_INSTALL_PATH=' \
            + untarFileDir + '/ncs~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~HOST_IP_ADDRESS=.*~HOST_IP_ADDRESS=' \
            + ncs_ip_1 + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_IP=.*~NCS_IP=' + ncs_ip_1 + '~" ' \
            + local_cluster1 + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NODEMANAGER_IP=.*~NODEMANAGER_IP=' + nms_ip_1 \
            + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' \
            + SERVER_ID_CLUSTER_1 + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + NCS_ON_THIS_MACHINE + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_HA_NODE=.*~NCS_HA_NODE=' \
            + NCS_HA_MODE_CLUSTER_1 + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' \
            + ncs_ip_2 + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' \
            + virtual_ip_ncs_1 + '~" ' + local_cluster1 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' + eth_ncs_ip1 + '~" ' + local_cluster1 + '/installDomainManager.properties')

                # ### Mediator.properties

        cmdHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + local_cluster1 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~PNMS_IP_ADDRESS=.*~PNMS_IP_ADDRESS=' \
            + nms_ip_1 + '~" ' + local_cluster1 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~MEDIATOR_IP_ADDRESS=.*~MEDIATOR_IP_ADDRESS=' \
            + med_ip_1 + '~" ' + local_cluster1 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster1 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~PEER_MEDIATOR=.*~PEER_MEDIATOR=' + med_ip_2 \
            + '~" ' + local_cluster1 + '/installMediator.properties')

                # ## PNMS.properties

        cmdHAList.append('sed -i "s~INSTALL_PADNMS_DIR=.*~INSTALL_PADNMS_DIR=' \
            + untarFileDir + '/etc~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_PNMS_DIR=.*~INSTALL_PNMS_DIR=' \
            + untarFileDir + '/pnmsinstall~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_1 + '~" ' \
            + local_cluster1 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' \
            + SERVER_ID_CLUSTER_1 + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + ON_SAME_MACHINE + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~MEDIATOR_ON_THIS_MACHINE=.*~MEDIATOR_ON_THIS_MACHINE=' \
            + MEDIATOR_ON_THIS_MACHINE + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_NODEMANAGER_DIR=.*~INSTALL_NODEMANAGER_DIR=' \
            + untarFileDir + '/installnodemanager~" ' + local_cluster1 \
            + '/installNodeManager.properties')
        cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' \
            + nms_ip_2 + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' \
            + virtual_ip_nms_1 + '~" ' + local_cluster1 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_TOPOLOGY=.*~INSTALL_TOPOLOGY=' + TOPOLOGY + '~" ' + local_cluster1 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' + eth_nms_ip1 + '~" ' + local_cluster1 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' + virtual_ip_nms_1 + '~" ' + local_cluster1 + '/installPNMS.properties')

                # ### Topology.properties

        if topology_ip_1 != 'False':
            eth_topology_ip_1_cmd = 'ip addr show | grep -i ' + topology_ip_1
	    eth_topology_ip1 = ssh_command(ssh[topology_ip_1], eth_topology_ip_1_cmd, 1).split(' ')[-1].rstrip()
	    
	    cmdHAList.append('sed -i "s~INSTALL_TOPOLOGY_DIR=.*~INSTALL_TOPOLOGY_DIR=' + untarFileDir + '/topologyinstall~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_1 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~TOPOLOGY_IP=.*~TOPOLOGY_IP=' + topology_ip_1 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' + SERVER_ID_CLUSTER_1 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' + topology_ip_2 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PNMS_VIRTUAL_IP=.*~PNMS_VIRTUAL_IP=' + virtual_ip_nms_1 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' + virtual_ip_topology_1 + '~" ' + local_cluster1 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' + eth_topology_ip1 + '~" ' + local_cluster1 + '/installTopology.properties')


            # updateConfiguration.properties

        cmdHAList.append('sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + nms_ip_1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + nms_ip_2 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~PADNMS_VIRTUAL_IP=.*~PADNMS_VIRTUAL_IP=' + virtual_ip_nms_1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~PADNMS_INTERFACE=.*~PADNMS_INTERFACE=' + eth_nms_ip1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~NCS_VIRTUAL_IP=.*~NCS_VIRTUAL_IP=' + virtual_ip_ncs_1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~NCS_INTERFACE=.*~NCS_INTERFACE=' + eth_ncs_ip1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~TOPOLOGY_VIRTUAL_IP=.*~TOPOLOGY_VIRTUAL_IP=' + virtual_ip_topology_1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')
        if topology_ip_1 != 'False':
            cmdHAList.append('sed -i "s~TOPOLOGY_INTERFACE=.*~TOPOLOGY_INTERFACE=' + eth_topology_ip1 + '~" ' + local_cluster1 + '/updateConfiguration.properties')


        
                # Changes for cluster2

        global local_cluster2
        local_cluster2 = installDir + '/cluster_2'
        if not os.path.exists(local_cluster2):
            os.makedirs(local_cluster2)
            print ' - Directory (', local_cluster2, ') Created '
        else:
            print ' - Directory (', local_cluster2, ') already exists'

        for file_2 in glob.glob(propDir + '*.properties'):
            shutil.copy2(file_2, local_cluster2)

                # ## DomainManager.properties

        cmdHAList.append('sed -i "s~INSTALL_DOMAINMANAGER_DIR=.*~INSTALL_DOMAINMANAGER_DIR=' \
            + untarFileDir + '/dminstall~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_BINARY_FILE_PATH=.*~NCS_BINARY_FILE_PATH=' \
            + untarFileDir + '/pkg/domainmanager/lib~" ' \
            + local_cluster2 + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_BINARY_INSTALL_PATH=.*~NCS_BINARY_INSTALL_PATH=' \
            + untarFileDir + '/ncs~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~HOST_IP_ADDRESS=.*~HOST_IP_ADDRESS=' \
            + ncs_ip_2 + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_IP=.*~NCS_IP=' + ncs_ip_2 + '~" ' \
            + local_cluster2 + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NODEMANAGER_IP=.*~NODEMANAGER_IP=' + nms_ip_2 \
            + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' \
            + SERVER_ID_CLUSTER_2 + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + NCS_ON_THIS_MACHINE + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~NCS_HA_NODE=.*~NCS_HA_NODE=' \
            + NCS_HA_MODE_CLUSTER_2 + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' \
            + ncs_ip_1 + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' \
            + virtual_ip_ncs_2 + '~" ' + local_cluster2 \
            + '/installDomainManager.properties')
        cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' + eth_ncs_ip2 + '~" ' + local_cluster2 + '/installDomainManager.properties')

                # ### Mediator.properties

        cmdHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + local_cluster2 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~PNMS_IP_ADDRESS=.*~PNMS_IP_ADDRESS=' \
            + nms_ip_2 + '~" ' + local_cluster2 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~MEDIATOR_IP_ADDRESS=.*~MEDIATOR_IP_ADDRESS=' \
            + med_ip_2 + '~" ' + local_cluster2 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster2 \
            + '/installMediator.properties')
        cmdHAList.append('sed -i "s~PEER_MEDIATOR=.*~PEER_MEDIATOR=' + med_ip_1 \
            + '~" ' + local_cluster2 + '/installMediator.properties')

                # ## PNMS.properties

        cmdHAList.append('sed -i "s~INSTALL_PADNMS_DIR=.*~INSTALL_PADNMS_DIR=' \
            + untarFileDir + '/etc~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_PNMS_DIR=.*~INSTALL_PNMS_DIR=' \
            + untarFileDir + '/pnmsinstall~" ' + local_cluster2 \
            + '/installPNMS.properties')
        
        cmdHAList.append('sed -i "s~INSTALL_MED_DIR=.*~INSTALL_MED_DIR=' \
            + untarFileDir + '/medinstall~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~BUILD_NAME=.*~BUILD_NAME=' \
            + parentUntarBuildPath + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_2 + '~" ' \
            + local_cluster2 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' \
            + SERVER_ID_CLUSTER_2 + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~ON_SAME_MACHINE=.*~ON_SAME_MACHINE=' \
            + ON_SAME_MACHINE + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~MEDIATOR_ON_THIS_MACHINE=.*~MEDIATOR_ON_THIS_MACHINE=' \
            + MEDIATOR_ON_THIS_MACHINE + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_NODEMANAGER_DIR=.*~INSTALL_NODEMANAGER_DIR=' \
            + untarFileDir + '/installnodemanager~" ' + local_cluster2 \
            + '/installNodeManager.properties')
        cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' \
            + nms_ip_1 + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' \
            + virtual_ip_nms_2 + '~" ' + local_cluster2 \
            + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INSTALL_TOPOLOGY=.*~INSTALL_TOPOLOGY=' + TOPOLOGY + '~" ' + local_cluster2 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' + eth_nms_ip2 + '~" ' + local_cluster2 + '/installPNMS.properties')
        cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' + virtual_ip_nms_2 + '~" ' + local_cluster2 + '/installPNMS.properties')

                # ## Topology.properties

        if topology_ip_2 != 'False':
            eth_topology_ip_2_cmd = 'ip addr show | grep -i ' + topology_ip_2
            eth_topology_ip2=ssh_command(ssh[topology_ip_2], eth_topology_ip_2_cmd, 1).split(' ')[-1].rstrip()

	    cmdHAList.append('sed -i "s~INSTALL_TOPOLOGY_DIR=.*~INSTALL_TOPOLOGY_DIR=' \
                + untarFileDir + '/topologyinstall~" ' + local_cluster2 \
                + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PNMS_IP=.*~PNMS_IP=' + nms_ip_2 + '~" ' \
                + local_cluster2 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~TOPOLOGY_IP=.*~TOPOLOGY_IP=' + topology_ip_2 \
                + '~" ' + local_cluster2 + '/installTopology.properties')
            cmdHAList.append('sed -i "s~SERVER_ID=.*~SERVER_ID=' \
                + SERVER_ID_CLUSTER_2 + '~" ' + local_cluster2 \
                + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' \
                + topology_ip_1 + '~" ' + local_cluster2 \
                + '/installTopology.properties')
            cmdHAList.append('sed -i "s~PNMS_VIRTUAL_IP=.*~PNMS_VIRTUAL_IP=' \
                + virtual_ip_nms_2 + '~" ' + local_cluster2 \
                + '/installTopology.properties')
            cmdHAList.append('sed -i "s~VIRTUAL_IP=.*~VIRTUAL_IP=' \
                + virtual_ip_topology_2 + '~" ' + local_cluster2 \
                + '/installTopology.properties')
            cmdHAList.append('sed -i "s~INTERFACE=.*~INTERFACE=' \
                + eth_topology_ip2 + '~" ' + local_cluster2 \
                + '/installTopology.properties')


            # updateConfiguration.properties

        cmdHAList.append('sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + nms_ip_2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + nms_ip_1 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~PADNMS_VIRTUAL_IP=.*~PADNMS_VIRTUAL_IP=' + virtual_ip_nms_2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~PADNMS_INTERFACE=.*~PADNMS_INTERFACE=' + eth_nms_ip2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~NCS_VIRTUAL_IP=.*~NCS_VIRTUAL_IP=' + virtual_ip_ncs_2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~NCS_INTERFACE=.*~NCS_INTERFACE=' + eth_ncs_ip2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        cmdHAList.append('sed -i "s~TOPOLOGY_VIRTUAL_IP=.*~TOPOLOGY_VIRTUAL_IP=' + virtual_ip_topology_2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        if topology_ip_2 != 'False':
            cmdHAList.append('sed -i "s~TOPOLOGY_INTERFACE=.*~TOPOLOGY_INTERFACE=' + eth_topology_ip2 + '~" ' + local_cluster2 + '/updateConfiguration.properties')
        

        for cmd in cmdHAList:
            os.system(cmd)
        
            

def checkProcessLoc(pnmsCheck=1, medCheck=1, ncsCheck=1):
    if pnmsCheck == medCheck == ncsCheck == 1:
        if med_ip_1 == nms_ip_1 == ncs_ip_1:
            return 'yes'
        else:
            return 'no'
    elif medCheck == 0:
        if nms_ip_1 == ncs_ip_1:
            return 'yes'
        else:
            return 'no'
    elif ncsCheck == 0:
        if nms_ip_1 == med_ip_1:
            return 'yes'
        else:
            return 'no'

def checkProcessLoc_c2(pnmsCheck=1, medCheck=1, ncsCheck=1):
    if pnmsCheck == medCheck == ncsCheck == 1:
        if med_ip_2 == nms_ip_2 == ncs_ip_2:
            return 'yes'
        else:
            return 'no'
    elif medCheck == 0:
        if nms_ip_2 == ncs_ip_2:
            return 'yes'
        else:
            return 'no'
    elif ncsCheck == 0:
        if nms_ip_2 == med_ip_2:
            return 'yes'
        else:
            return 'no'



def copyPropFilesRemotely():
    propDir = untarFileDir + '/bin/'
    if int(isHA) == 0:
        propFiles = (propDir + 'installPNMS.properties', propDir
                     + 'installDomainManager.properties', propDir
                     + 'installMediator.properties', propDir
                     + '/installNodeManager.properties', propDir
                     + '/installTopology.properties')
        for ip in unique_ips:
            print '\n' + getTimeStamp() \
                + ' Copying properties file to ip : ', ip
            for file in propFiles:
                print '\t - Copying ', file
                pushBuild(ssh[ip], src=file, dst=file)

#       pushBuild(ssh,src="/home/padtec/abhishek/installInNonHaMode.sh",dst="/home/padtec/builds/OTS12_PADNMS_V1.1.11/bin/installInNonHaMode.sh")
#       pushBuild(ssh,src="/home/padtec/padtec_automation/pnms-automation/pnmsInstallation/installInNonHaMode_AS.sh",dst=propDir + "installInNonHaMode.sh")

                pushBuild(ssh[ip],
                          src='/home/padtec/pnms-installation/nonHA/startInNonHaMode_nonHA.sh'
                          , dst=propDir + 'startInNonHaMode_nonHA.sh')
                pushBuild(ssh[ip],
                          src='/home/padtec/pnms-installation/nonHA/startInNonHaMode_onlyPNMS.sh'
                          , dst=propDir + 'startInNonHaMode_onlyPNMS.sh'
                          )
    elif int(isHA) == 1:
        for ip in unique_ips:
            if ip == nms_ip_1 or ip == med_ip_1 or ip == ncs_ip_1 or (ip == topology_ip_1 and topology_ip_1 != 'false' and topology_ip_1 != nms_ip_1):
                print '\n' + getTimeStamp() \
                    + ' Copying properties file to ip : ', ip
                for file_1 in glob.glob(local_cluster1
                        + '/*.properties'):
                    print '\t - Copying ', file_1
                    pushBuild(ssh[ip], src=file_1, dst=propDir
                              + file_1.split('/')[-1])
            elif ip == nms_ip_2 or ip == med_ip_2 or ip == ncs_ip_2 or (ip == topology_ip_2 and topology_ip_2 != 'false' and topology_ip_2 != nms_ip_2):
                print '\n' + getTimeStamp() \
                    + ' Copying properties file to ip : ', ip
                for file_2 in glob.glob(local_cluster2
                        + '/*.properties'):
                    print '\t - Copying ', file_2
                    pushBuild(ssh[ip], src=file_2, dst=propDir
                              + file_2.split('/')[-1])



def getExePath(runningprocess, service):
    pathFound = int(0)
    if service == 'pnms':
        expText = '-jar'
    elif service == 'ncs':
        expText = '-classpath'
    for text in runningprocess.split(' '):
        if pathFound:
            break
        if text == expText:
            pathFound = 1
            continue
    if not pathFound:
        print service + ' process path not found!'
    if pathFound:
        if service == 'pnms':
            return text.split('pnmsinstall')[0] + 'bin/'
        elif service == 'ncs':
            return (text.split('ncs')[0])[1:] + 'bin/'


def uninstall():
    for ip in unique_ips:
#               ssh = raw_ssh(ip)

            print '\n' + getTimeStamp() \
                + ' Calling UnInstall script : ', ip
            commandLine = 'ps -eaf | grep java | grep -v grep | wc -l'
            print '\t ---- Counting Java Processes running remotely'
            countJavaProcess = ssh_command(ssh[ip], commandLine, 1)
            if int(countJavaProcess) == 0:
                print '\t - No java process found running!\n'
            else:
                print '\t - Java Process is running remotely\n'
                cmd = \
                    'ps -eaf | grep java | grep -v grep | grep appserver'

#                       print "running '%s'" % cmd

                print '\t ---- Checking if PNMS process running or not remotely'
                pnmsPath = ssh_command(ssh[ip], cmd, 1)
                if pnmsPath != '':
                    print '\t ---- PNMS found running!'
                    exePath = getExePath(pnmsPath, 'pnms')
                    print '\t ---- Executing pre-uninstallation cleanup'
                    cmd1 = """cd  """ + exePath + """;""" \
                        + """if [ -d "../pnmsinstall/pnms/bkpScript/" ]
                                then
                                        cd ../pnmsinstall/pnms/bkpScript/
                                        echo $PASSWORD | sudo -S sudo ./env_NMSBackup.sh CleanUp
                                        cd -
                                fi
                                """
                    ssh_command(ssh[ip], cmd1, 2)
                    
                    print '\t ---- Executing PNMS uninstall\n'
                    cmd2 = 'cd ' + exePath + """;""" + exePath \
                        + 'installPNMS.sh -uninstall ' + exePath \
                        + 'installPNMS.properties'
                    ssh_command(ssh[ip], cmd2, 2)
                else:
                    print '\t - PNMS not found running!\n'

                commandLine = \
                    'ps -eaf | grep java | grep -v grep | grep mediator'
                print '\t ---- Checking if Mediator process running or not remotely'
                medPath = ssh_command(ssh[ip], commandLine, 1)
                if medPath != '':
                    print '\t - Mediator found running!'
                    if nms_ip_1 == med_ip_1:

#                                       exePath=getExePath(pnmsPath,"pnms")

                        print '\t ---- Executing Mediator uninstall\n'
                        cmd = 'cd ' + exePath + """;""" + exePath \
                            + 'installMediator.sh -uninstall ' \
                            + exePath + 'installMediator.properties'
                        ssh_command(ssh[ip], cmd, 2)
                else:
                    print '\t - Mediator not found running!\n'

                commandLine = \
                    'ps -eaf | grep java | grep -v grep | grep ncs'
                print '\t ---- Checking if NCS process running or not remotely'
                ncsPath = ssh_command(ssh[ip], commandLine, 1)
                if ncsPath != '':
                    print '\t - NCS found running!'
                    exePath = getExePath(ncsPath, 'ncs')
                    print '\t ---- Executing NCS uninstall'
                    cmd1 = 'cd ' + exePath + """;""" + exePath \
                        + 'installDomainManager.sh -uninstall ' \
                        + exePath + 'installDomainManager.properties'
                    ssh_command(ssh[ip], cmd1, 2)
                    
                    print '\t ---- Executing post-uninstallation cleanup of DB users\n'
                    cmd2 = \
                        """mysql -uroot -ppadtec <<EOF
                                delete from mysql.user where User="replication";
                                delete from mysql.user where User="nmsHA";
                                EOF
                                """
                    ssh_command(ssh[ip], cmd2, 2)
                else:

                    print '\t - NCS not found running!\n'
            
            print " - Removing ncs_env file (if exists) for safer reason"
            cmd_remove_ncsEnv = 'rm -f ~/.ncs_env'
            ssh_command(ssh[ip], cmd_remove_ncsEnv, 2)

            
    
def uninstall_default():
    for ip in unique_ips:
        print "- Executing uninstallInHaMode.sh for safer side in ip: ", ip
        cmd_common = 'cd ' + uninstallPath + '; ./uninstallInHaMode.sh;'
        ssh_command(ssh[ip], cmd_common, 2)
        time.sleep(5)

	if int(isHA) == 1:
	    if ip == ncs_ip_1 or ip == ncs_ip_2:
	        if ncs_ip_1 != nms_ip_1:
		    print "- NCS is installed in different server : ", ip
        	    cmd_ncs = 'cd ' + uninstallPath + '; ./uninstallNCS.sh;'
        	    ssh_command(ssh[ip], cmd_ncs, 2)
        	    time.sleep(5)
	
	        if ncs_ip_2 != nms_ip_2:
                    print "- NCS is installed in different server : ", ip
                    cmd_ncs = 'cd ' + uninstallPath + '; ./uninstallNCS.sh;'
                    ssh_command(ssh[ip], cmd_ncs, 2)
                    time.sleep(5)

	### Currently not suppporting unintallation of topology in standalone mode, please uncomment and change code once issue is fixed in shell scripts
        """if ip == topology_ip_1 or ip == topology_ip_2:
            if topology_ip_1 != 'false' and topology_ip_1 != nms_ip_1 :
                print "- Uninstalling Topology in server: ", ip
                cmd_tplgy = 'cd ' + uninstallPath + '; ./installTopology.sh -uninstall installTopology.properties;'
                ssh_command(ssh[ip], cmd_tplgy, 2)
                time.sleep(5)

        if topology_ip_2 != 'false' and topology_ip_2 != nms_ip_2 :
                print "- Uninstalling Topology in server: ", ip
                cmd_tplgy = 'cd ' + uninstallPath + '; ./installTopology.sh -uninstall installTopology.properties;'
                ssh_command(ssh[ip], cmd_tplgy, 2)
                time.sleep(5)
	"""


    for ip in unique_ips:
        print "- Deleting ncs and pnms user from mysql.user database in : ", ip
        cmd='''mysql -uroot -ppadtec -e "delete from mysql.user where User in('ncs', 'pnms');"'''
        ssh_command(ssh[ip], cmd, 2)


def install():
    if (int(isHA) == 0):
        installNonHA()
    elif (int(isHA) == 1):
    	installHA()
        start_app()
        #start_ha()
    else:
        print "Invalid value set for isHA parameter, isHA = " + str(isHA)


def installNonHA():
    propDir = untarFileDir + '/bin/'
    nms_flag = int(0)
    med_flag = int(0)
    ncs_flag = int(0)
    topology_flag = int(0)
    for ip in unique_ips:
        print '\n' + getTimeStamp() + ' Calling Install script : ', ip
        if ip == nms_ip_1 and nms_flag == 0:
            nms_flag = 1
            print '''----------- Installing PNMS ---------------'''
            cmd = 'cd ' + propDir + """;""" + propDir \
                + 'installPNMS.sh -install ' + propDir \
                + 'installPNMS.properties'

            ssh_command(ssh[ip], cmd, 2)
            print '\n' + getTimeStamp() + ' Configuring database.....'
            cmd = 'cd ' + propDir + """;""" + propDir \
                + '../etc/configure_database.sh'
            ssh_command(ssh[ip], cmd, 2)

        if ip == topology_ip_1 and topology_ip_1 != nms_ip_1 and topology_flag == 0 and topology_ip_1 != 'False':
            topology_flag = 1
            print "\n----------- Installing Topology ---------------\n"
            cmd='cd ' + propDir + ';' + propDir + 'installTopology.sh -install ' +propDir+ 'installTopology.properties'
            ssh_command(ssh[ip],cmd,2)

        if ip == med_ip_1 and med_flag == 0:
            med_flag = 1
            print '''----------- Installing Mediator ---------------'''
            cmd = 'cd ' + propDir + """;""" + propDir \
                + 'installMediator.sh -install ' + propDir \
                + 'installMediator.properties'
            ssh_command(ssh[ip], cmd, 2)
        
	if ip == ncs_ip_1 and ncs_flag == 0:
            ncs_flag = 1
            print '''----------- Installing NCS ---------------'''
            cmd = 'cd ' + propDir + """;""" + propDir \
                + 'installDomainManager.sh -install ' + propDir \
                + 'installDomainManager.properties'

            ssh_command(ssh[ip], cmd, 2)
            time.sleep(5)
            cmd = 'cd ' + propDir \
                + '../dminstall/domainmanager/bin; source ~/.ncs_env; ./rundomainmanager.sh start'
            ssh_command(ssh[ip], cmd, 2)
            time.sleep(5)


    cmd = 'cd ' + propDir + '; ' + propDir \
        + 'populateNodeManagerdb.sh ' + propDir \
        + 'installPNMS.properties'
    ssh_command(ssh[nms_ip_1], cmd, 2)
    time.sleep(5)
    cmd = 'cd ' + propDir + '; ' + propDir \
        + 'updateNotificationPointer.sh'
    ssh_command(ssh[ncs_ip_1], cmd, 2)
    time.sleep(5)

    for ip in unique_ips:
        print '''----------- Starting Processes ---------------'''
	print "Starting processes over IP: ", ip
        cmd = 'cd ' + propDir + '; chmod 755 startInNonHaMode_nonHA.sh; ./startInNonHaMode_nonHA.sh'
        ssh_command_new(ssh[ip], cmd)

    print "- Starting PNMS only: "
    cmd = 'cd ' + propDir + '; chmod 755 startInNonHaMode_onlyPNMS.sh; ./startInNonHaMode_onlyPNMS.sh'
    ssh_command_new(ssh[nms_ip_1], cmd)

def create_nmsHA(ip, peer_ip):
    print " - Creating nmsHA user at : ", ip
    cmd_c1_1="""mysql -uroot -ppadtec << EOF
        delete from mysql.user where User=\'nmsHA\' and Host=\'"""+ peer_ip +"""\';
        FLUSH PRIVILEGES;
        EOF"""
    ssh_command(ssh[ip], cmd_c1_1, 2)
    time.sleep(5)

    cmd_c1_2="""mysql -uroot -ppadtec << EOF
        CREATE USER \'nmsHA\'@\'"""+ peer_ip +"""\' IDENTIFIED BY \'padtec\';
        GRANT ALL PRIVILEGES ON *.* TO \'nmsHA\'@\'""" + peer_ip + """\' WITH GRANT OPTION;
        FLUSH PRIVILEGES;
        EOF"""
    ssh_command(ssh[ip], cmd_c1_2, 2)
    time.sleep(5)

def mysql_repl(ip):
    propDir = untarFileDir + '/bin/'
    ### MySQL Replication
    print " - Setting up MySQL Replciataion at: ", ip

    cmd_repl = 'cd ' + propDir + '; ./enableSQLReplication.sh;'
    ssh_command_noBuffer(ssh[ip], cmd_repl)
    time.sleep(3)


def installHA():
    propDir = untarFileDir + '/bin/'
    nms_flag_1 = int(0)
    med_flag_1 = int(0)
    ncs_flag_1 = int(0)
    topology_flag_1 = int(0)

    for (name, ip) in Cluster_1.items():
        if ip == nms_ip_1 and nms_flag_1 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            nms_flag_1 = 1
            print '''----------- Installing PNMS ---------------'''
            cmd1 = 'cd ' + propDir + '; ./installPNMS.sh -install installPNMS.properties'
            ssh_command(ssh[ip], cmd1, 2)
            time.sleep(5)

            create_nmsHA(ip, nms_ip_2)
        
        # Installing topology on individual server (if topology ip is not same as nms ip and topology is not commented in config.ini file)
        if ip == topology_ip_1 and topology_ip_1 != nms_ip_1 and topology_flag_1 == 0 and topology_ip_1 != 'false':
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            topology_flag_1 = 1
            print '''----------- Installing Topology ---------------'''
            cmd_topology='cd ' + propDir + '; ./installTopology.sh -install installTopology.properties'
            ssh_command(ssh[ip],cmd_topology,2)
            
            create_nmsHA(ip, topology_ip_2)


        if ip == med_ip_1 and med_flag_1 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            med_flag_1 = 1
            print '''----------- Installing Mediator ---------------'''
            cmd2 = 'cd ' + propDir + '; ./installMediator.sh -install installMediator.properties'
            ssh_command(ssh[ip], cmd2, 2)
            time.sleep(5)

        if ip == ncs_ip_1 and ncs_flag_1 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            ncs_flag_1 = 1
            print '''----------- Installing NCS ---------------'''
            cmd3 = 'cd ' + propDir + '; ./installDomainManager.sh -install installDomainManager.properties'
            ssh_command(ssh[ip], cmd3, 2)
            time.sleep(5)
            
            if ncs_ip_1 != nms_ip_1:
                create_nmsHA(ip, ncs_ip_2)
            
            print "- Starting DomainManager in: ", ip 
            cmd4 = 'cd ' + propDir + '; cd ../dminstall/domainmanager/bin; source ~/.ncs_env; ./rundomainmanager.sh start; cd -;'
            ssh_command(ssh[ip], cmd4, 2)
            time.sleep(5)



    #### Cluster 2 Installation

    nms_flag_2 = int(0)
    med_flag_2 = int(0)
    ncs_flag_2 = int(0)
    topology_flag_2 = int(0)
    for (name, ip) in Cluster_2.items():
        if ip == nms_ip_2 and nms_flag_2 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            nms_flag_2 = 1
            print '''----------- Installing PNMS ---------------'''
            cmd5 = 'cd ' + propDir + '; ./installPNMS.sh -install installPNMS.properties'
            ssh_command(ssh[ip], cmd5, 2)
            
            create_nmsHA(ip, nms_ip_1)


        # Installing topology on individual server
        if ip == topology_ip_2 and topology_ip_2 != nms_ip_2 and topology_flag_2 == 0 and topology_ip_2 != 'false':
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            topology_flag_2 = 1
            print '''----------- Installing Topology ---------------'''
            cmd_topology='cd ' + propDir + '; ./installTopology.sh -install installTopology.properties'
            ssh_command(ssh[ip],cmd_topology,2)
            
            create_nmsHA(ip, topology_ip_1)


        if ip == med_ip_2 and med_flag_2 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            med_flag_2 = 1
            print '''----------- Installing Mediator ---------------'''
            cmd6 = 'cd ' + propDir + '; ./installMediator.sh -install installMediator.properties'
            ssh_command(ssh[ip], cmd6, 2)
      
        if ip == ncs_ip_2 and ncs_flag_2 == 0:
            print '\n' + getTimeStamp() + ' Calling Install script : ', ip
            ncs_flag_2 = 1
            print '''----------- Installing NCS ---------------'''
            cmd7 = 'cd ' + propDir +'; ./installDomainManager.sh -install installDomainManager.properties'
            ssh_command(ssh[ip], cmd7, 2)
            time.sleep(5)

            if ncs_ip_2 != nms_ip_2:
                create_nmsHA(ip, ncs_ip_1)


            print "- Starting DomainManager in: ", ip 
            cmd8 = 'cd ' + propDir + '; cd ../dminstall/domainmanager/bin; source ~/.ncs_env; ./rundomainmanager.sh start; cd -;'
            ssh_command(ssh[ip], cmd8, 2)
            time.sleep(5)

    
    ### Change few of NM configs remotely
    change_nodeMgr()
    
    ### Change few of NCS configs remotely
    change_ncs()
    
    ### Change few of Topology configs remotely
    if topology_ip_1 != nms_ip_1 and topology_ip_2 != nms_ip_2 and topology_ip_1 != 'false' and topology_ip_2 != 'false':
        change_topology()

    ### MySQL Replication of nms_ip_1 and nms_ip_2
    mysql_repl(nms_ip_1)
    mysql_repl(nms_ip_2)

    if nms_ip_1 != ncs_ip_1 and nms_ip_2 != ncs_ip_2:
        mysql_repl(ncs_ip_1)
        mysql_repl(ncs_ip_2)
    
    if topology_ip_1 != nms_ip_1 and topology_ip_2 != nms_ip_2 and topology_ip_1 != 'false' and topology_ip_2 != 'false':
        mysql_repl(topology_ip_1)
        mysql_repl(topology_ip_2)



def change_topology():
    
    # Change installTopology.properites
    propDir = untarFileDir + '/bin/'
    topologyPropFile =  untarFileDir + 'installTopology.properties'

    
    cmd1 = 'sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' + topology_ip_2 + '~" ' + topologyPropFile
    ssh_command(ssh[topology_ip_1], cmd1)
    
    cmd2 = 'sed -i "s~PEER_SQL_SERVER=.*~PEER_SQL_SERVER=' + topology_ip_1 + '~" ' + topologyPropFile
    ssh_command(ssh[topology_ip_2], cmd2)
    
    
    SERVER_ID_CLUSTER_1 = '1'
    SERVER_ID_CLUSTER_2 = '2'

   
    ### update pnmstopologydb

    ### Cluster 1

    cmd3 = """mysql -uroot -ppadtec << EOF
        UPDATE pnmstopologydb.topology_config SET value='"""+ virtual_ip_nms_1 +"""' WHERE name='pnms-address' and cluster_id=""" + str(SERVER_ID_CLUSTER_1) +""";
EOF"""
    ssh_command(ssh[topology_ip_1], cmd3)

    ### Cluster 2

    cmd4 = """mysql -uroot -ppadtec << EOF
        UPDATE pnmstopologydb.topology_config SET value='"""+ virtual_ip_nms_2 +"""' WHERE name='pnms-address' and cluster_id=""" + str(SERVER_ID_CLUSTER_2) +""";
EOF"""
    ssh_command(ssh[topology_ip_2], cmd4)
    


    #Change updateConfiguration.properties if Topology is installed on another server
    tplgySQLRepFile = propDir + 'updateConfiguration.properties'
    
    cmd5 = 'sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + topology_ip_1 + '~" ' + tplgySQLRepFile
    cmd6 = 'sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + topology_ip_2 + '~" ' + tplgySQLRepFile

    ssh_command(ssh[topology_ip_1], cmd5)
    ssh_command(ssh[topology_ip_1], cmd6)
    
    cmd7 = 'sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + topology_ip_2 + '~" ' + tplgySQLRepFile
    cmd8 = 'sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + topology_ip_1 + '~" ' + tplgySQLRepFile

    ssh_command(ssh[topology_ip_2], cmd7)
    ssh_command(ssh[topology_ip_2], cmd8)
 

    
def change_nodeMgr():
    print "- Changing runnodemanager.properties file in: ", nms_ip_1
    nodeMgrPropFile =  untarFileDir + '/pnmsinstall/pnms/etc/runnodemanager.properties'
    pnmsDir = untarFileDir + '/pnmsinstall'
    
    cmd1 = 'sed -i "s~jboss.home.dir=.*~jboss.home.dir=' + pnmsDir + '/pnms/appserver-wildfly~" ' + nodeMgrPropFile
    cmd2 = 'sed -i "s~appserver.ip=.*~appserver.ip=' + nms_ip_1 + '~" ' + nodeMgrPropFile

    ssh_command(ssh[nms_ip_1], cmd1)
    ssh_command(ssh[nms_ip_1], cmd2)
    
    # Change for cluster_2

    print "- Changing runnodemanager.properties file in: ", nms_ip_2
    cmd3 = 'sed -i "s~appserver.ip=.*~appserver.ip=' + nms_ip_2 + '~" ' + nodeMgrPropFile
    
    ssh_command(ssh[nms_ip_2], cmd1)
    ssh_command(ssh[nms_ip_2], cmd3)


def change_ncs():
    ncsHaFile =  untarFileDir + '/dminstall/domainmanager/gotns/ncs-cdb/ncs_ha_init.xml'
    ncsSQLRepFile =  untarFileDir + '/bin/updateConfiguration.properties'
    pnmsDir = untarFileDir + '/pnmsinstall'

    # Change for cluster_1
    print "- Changing ncs_ha_init.xml file in: ", ncs_ip_1
    cmd1 ='sed -i "s~<n1-address>127.0.0.1~<n1-address>'+ncs_ip_1+'~" ' + ncsHaFile
    cmd2 ='sed -i "s~<n2-address>127.0.0.1~<n2-address>'+ncs_ip_2+'~" ' + ncsHaFile
    
    
    ssh_command(ssh[ncs_ip_1], cmd1)
    ssh_command(ssh[ncs_ip_1], cmd2)


    # Change updateConfiguration.properties if NCS is installed on another server
    cmd3 = 'sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + ncs_ip_1 + '~" ' + ncsSQLRepFile
    cmd4 = 'sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + ncs_ip_2 + '~" ' + ncsSQLRepFile

    ssh_command(ssh[ncs_ip_1], cmd3)
    ssh_command(ssh[ncs_ip_1], cmd4)
     


    ### Change for cluster_2
    print "- Changing ncs_ha_init.xml file in: ", ncs_ip_2
    cmd5 ='sed -i "s~<n1-address>127.0.0.1~<n1-address>'+ncs_ip_1+'~" ' + ncsHaFile
    cmd6 ='sed -i "s~<n2-address>127.0.0.1~<n2-address>'+ncs_ip_2+'~" ' + ncsHaFile
    

    ssh_command(ssh[ncs_ip_2], cmd5)
    ssh_command(ssh[ncs_ip_2], cmd6)

    # Change updateConfiguration.properties if NCS is installed on another server
    cmd7 = 'sed -i "s~LOCAL_IP=.*~LOCAL_IP=' + ncs_ip_2 + '~" ' + ncsSQLRepFile
    cmd8 = 'sed -i "s~REMOTE_IP=.*~REMOTE_IP=' + ncs_ip_1 + '~" ' + ncsSQLRepFile

    ssh_command(ssh[ncs_ip_2], cmd7)
    ssh_command(ssh[ncs_ip_2], cmd8)


def start_app():
    propDir = untarFileDir + '/bin/'
    for ip in unique_ips:
        print "- Starting applications on : ", ip
        cmd = 'cd ' + propDir + '; ./start_app.sh;'
        print cmd
        ssh_command_new(ssh[ip], cmd)
        time.sleep(60)

    ##### Start Mediator
    print " - Starting Mediator", med_ip_1
    cmd = 'cd ' + propDir + '; cd ../medinstall/mediator/bin; ./runmediator.sh start; sleep 6; redis-cli set notificationId 0;'
    #print cmd
    ssh_command_new(ssh[med_ip_1], cmd)
    time.sleep(5)

    print " - Starting Mediator", med_ip_2
    ssh_command_new(ssh[med_ip_2], cmd)
    time.sleep(5)


def start_ha():
    propDir = untarFileDir + '/bin/'
    for ip in unique_ips:
        print ' - Configuring database for : ', ip
        cmd = 'cd ' + propDir + '; ./../etc/configure_database.sh;'
        ssh_command(ssh[ip], cmd, 2)
        print "Waiting for a moment...."
        time.sleep(5)

    print " - Executing populateNodeManagerdb.sh on: ", nms_ip_1
    cmd = 'cd ' + propDir + '; ./populateNodeManagerdb.sh installPNMS.properties;'
    ssh_command(ssh[nms_ip_1], cmd, 2)
    time.sleep(5)
    
    print " - Executing populateNodeManagerdb.sh on: ", nms_ip_2
    ssh_command(ssh[nms_ip_2], cmd, 2)
    time.sleep(5)



    
    ##### Start PNMS/Topology 
    if topology == 'true':

        # Changing topology db and runtopology.properties
        print " - Changing topology db and runtopology.properties"
        change_topology()
        
        # start PNMS in HA mode with Topology
        print "- Starting PNMS in HA mode with Topology: ", nms_ip_1
        cmd = 'cd ' + propDir + ';  cd ../pnmsinstall/pnms/bin; ./runpnms.sh start with-ha-topology; cd -;'
        #print cmd
        ssh_command(ssh[nms_ip_1], cmd, 2)

        print "- Starting PNMS in HA mode with Topology: ", nms_ip_2
        ssh_command(ssh[nms_ip_2], cmd, 2)
    else:
        # start PNMS in HA mode without Topology
        print "- Starting PNMS in HA mode without Topology: ", nms_ip_1
        cmd = 'cd ' + propDir + ';  cd ../pnmsinstall/pnms/bin; ./runpnms.sh start with-ha; cd -;'
        #print cmd
        ssh_command(ssh[nms_ip_1], cmd, 2)
    
        print "- Starting PNMS in HA mode without Topology: ", nms_ip_2
        ssh_command(ssh[nms_ip_2], cmd, 2)
    
    ##### Start Domain Manager
    print " - Executing updateNotificationPointer.sh on: ", ncs_ip_1
    cmd = 'cd ' + propDir + '; source ~/.ncs_env; ./updateNotificationPointer.sh;'
    ssh_command(ssh[ncs_ip_1], cmd, 2)
    print " - Executing updateNotificationPointer.sh on: ", ncs_ip_2
    ssh_command(ssh[ncs_ip_2], cmd, 2)
    time.sleep(5)
    
    print " - Starting Domain Manager", ncs_ip_1
    cmd = 'cd ' + propDir + '; cd ../dminstall/domainmanager/gotns/; source ~/.ncs_env; echo 1 | gotns start; cd -;'
    ssh_command(ssh[ncs_ip_1], cmd,2)
    #print cmd
    time.sleep(5)

    print " - Starting Domain Manager", ncs_ip_2
    ssh_command(ssh[ncs_ip_2], cmd,2)
    time.sleep(5)
    
    
    
    ##### Start Mediator
    print " - Starting Mediator", med_ip_1
    cmd = 'cd ' + propDir + '; cd ../medinstall/mediator/bin; ./runmediator.sh start; sleep 6; redis-cli set notificationId 0;'
    #print cmd
    ssh_command_new(ssh[med_ip_1], cmd)
    time.sleep(5)
    
    print " - Starting Mediator", med_ip_2
    ssh_command_new(ssh[med_ip_2], cmd)
    time.sleep(5)

def validate_ips():
    exit_flag_c1 = 0
    exit_flag_c2 = 0
    for k,v in Cluster_1.items():
        try:
            IP(v)
        except ValueError as e:
            print "\t INVALID FORMAT: " + str(e)
	    exit_flag_c1 = 1

    for k,v in Cluster_2.items():
        try:
            IP(v)
        except ValueError as e:
            print "\t INVALID FORMAT: " + str(e)
            exit_flag_c2 = 1


    if exit_flag_c1 == 1 or exit_flag_c2 == 1:
        exit()
    else:
	print "\t - IP Validation passed successfully"

	    

def readIps(config):
    global ncs_ip_1, med_ip_1, nms_ip_1, topology_ip_1, virtual_ip_nms_1, \
        virtual_ip_ncs_1, virtual_ip_topology_1, ncs_ip_2, med_ip_2, nms_ip_2, \
        topology_ip_2, virtual_ip_nms_2, virtual_ip_ncs_2, virtual_ip_topology_2, unique_ips, ssh
    
   
    nms_ip_1 = str(readOptions(config, 'Cluster_1', 'nms_ip_1'))
    med_ip_1 = str(readOptions(config, 'Cluster_1', 'med_ip_1'))
    ncs_ip_1 = str(readOptions(config, 'Cluster_1', 'ncs_ip_1'))
    topology_ip_1 = str(readOptions(config, 'Cluster_1', 'topology_ip_1'))
    

    unique_ips = []
    if int(isHA) == 0:
        print '\n' + getTimeStamp() + ' SetUp type is nonHA'
        print '\t - Following elements will be installed in Cluster_1'
        print '\t Cluster_1 IPs: '
	print '\t\t - nms_ip_1 : ', nms_ip_1
	print '\t\t - med_ip_1 : ', med_ip_1
	print '\t\t - ncs_ip_1 : ', ncs_ip_1
	print '\t\t - topology_ip_1 : ', topology_ip_1

	for ip in [nms_ip_1, med_ip_1, ncs_ip_1, topology_ip_1]:
	    if ip != 'False':
	        if ip not in unique_ips:
	            unique_ips.append(ip)	    

    
    elif int(isHA) == 1:
        nms_ip_2 = str(readOptions(config, 'Cluster_2', 'nms_ip_2'))
        med_ip_2 = str(readOptions(config, 'Cluster_2', 'med_ip_2'))
        ncs_ip_2 = str(readOptions(config, 'Cluster_2', 'ncs_ip_2'))
        topology_ip_2 = str(readOptions(config, 'Cluster_2', 'topology_ip_2'))

        # if isHA=1 then virtual ip of Cluster_1 and Cluster_2 is mandatory
        virtual_ip_nms_1 = readOptions(config, 'Cluster_1', 'virtual_ip_nms_1')
        virtual_ip_ncs_1 = readOptions(config, 'Cluster_1', 'virtual_ip_ncs_1')
        virtual_ip_topology_1 = readOptions(config, 'Cluster_1', 'virtual_ip_topology_1')
        
        virtual_ip_nms_2 = readOptions(config, 'Cluster_2', 'virtual_ip_nms_2')
        virtual_ip_ncs_2 = readOptions(config, 'Cluster_2', 'virtual_ip_ncs_2')
        virtual_ip_topology_2 = readOptions(config, 'Cluster_2', 'virtual_ip_topology_2')

  
        print '\n' + getTimeStamp() + ' SetUp type is HA'
        print '\t - Following elements will be installed in Cluster_1 and Cluster_2'
        print '\t Cluster_1 IPs: '
        
	
        for (k, v) in Cluster_1.items():
	    if v == 'false' or v == virtual_ip_nms_1 or v == virtual_ip_ncs_1 or v == virtual_ip_topology_1:
                pass
            else:
      	        print '\t\t - ', k, ':', v
                if v not in unique_ips:
                    unique_ips.append(v)

        print '\t Cluster_2 IPs: '
        for (k, v) in Cluster_2.items():
	    if v == 'false' or v == virtual_ip_nms_2 or v == virtual_ip_ncs_2 or v == virtual_ip_topology_2:
                pass
            else:
                print '\t\t - ', k, ':', v
                if v not in unique_ips:
                    unique_ips.append(v)
    else:
        print "\t Invalid value set for isHA, Valid value 0 OR 1 only"

def verifyNMGuiAccess():
	verifyNMGuiAccessForIp(nms_ip_1)
	if (int(isHA) == 1):
	    verifyNMGuiAccessForIp(nms_ip_2)


def verifyNMGuiAccessForIp(nms_ip):
    print '\n' + getTimeStamp() \
        + ' Awaiting for Node-Manager GUI to start...'
    expOp = '<Response [200]>'
    t_start = time.time()
    t_end = time.time() + 60 * 2
    while time.time() < t_end:
        try:
            response = requests.post('http://' + nms_ip + ':8080/nodemanager/')
            if str(response) == expOp:
                print '\t - Node-Manager GUI is accessible at IP: ' + nms_ip + ' post ' + str(int(time.time() - t_start)) + ' seconds of installation completion.'
                print '\t - Script execution is completed!'
                break
            else:
                print '\t - ' + str(response)
        except:
            print 'No response received from server!'
        print str(int(time.time() - t_start)) + ' seconds passed after installation and Node-Manager GUI is not accessible. Will retry for ' + str(int(t_end - time.time())) + ' seconds more.'
        time.sleep(5)
    print '\t - Kindly check the installation logs!'




def setupPwdLessComm():
    global ssh
    ssh = {}
    print ' - Setting up all servers for password less communications '
    key = open(os.path.expanduser('~/.ssh/id_rsa.pub')).read()
    for ip in unique_ips:
    	ssh_key_exchange(hostname=ip, username='padtec',password='abcd1234!', key=key)

        # connecting to buildServerIP

    print ' - Setting up BuildServer for passwordless communication: '
    ssh_key_exchange(hostname=buildServerIP, username='padtec',
                     password='abcd1234!', key=key)


def cleanUpSsh():
    print " - Cleaning up SSH connections"
    for ip in unique_ips:
        ssh[ip].close()
    ssh[buildServerIP].close()


if __name__ == '__main__':
    scriptStartTS = time.time()

        # Define and read config.ini
    config_file = 'config.ini'
    config = parser(config_file)
    

    print '\n' + getTimeStamp() + ' Reading sections of file: ', config_file
    gen_items = dict(readSectionFromFlatfile(config, 'general'))
    Cluster_1 = collections.OrderedDict(readSectionFromFlatfile(config,'Cluster_1'))
    Cluster_2 = collections.OrderedDict(readSectionFromFlatfile(config,'Cluster_2'))
    
        # Valdiate IPs in both clusters
    validate_ips()

        # Reading general section variables

    print '\n' + getTimeStamp() + ' Reading options from file: ', config_file
    isHA = readOptions(config, 'general', 'isHA') 
    installDir = readOptions(config, 'general', 'installDir')
    buildName = readOptions(config, 'general', 'buildName')
    buildServerIP = readOptions(config, 'general', 'buildServerIP')
    buildPath = readOptions(config, 'general', 'buildPath')
    buildName = readOptions(config, 'general', 'buildName')
    uninstallPath = readOptions(config, 'general', 'uninstallPath')
        

	# Variables for internal usage

    buildServerBuildPath = buildPath + '/' + buildName
    localBuildPath = installDir + '/' + buildName

        # Identifying Setup Type [NonHA or HA] and unique-IPs from config.ini
    readIps(config)
        # Setting up passwordless communication for servers

    setupPwdLessComm()

        # pulling the build from build server to local server
    pullBuildFromBuildServer()

        # untar build File locally

    parentUntarBuildPath = untarBuildLocally()
    untarFileDir = installDir + '/' + parentUntarBuildPath

        # Change Prop Files

    changePropFiles()

        # pushing the build to all uniq IPs

    copyBuildRemotely()

        # untar the remote files

    untarBuildRemotely()
        
        # Uninstall the existing build

    if str(uninstallPath) == 'False':
        print " - Skipping uninstallation as \'uninstallPath\' is not set under section [general] "
	time.sleep(5)
    else:
        #uninstall()
        uninstall_default()

        # Copy prop files remotely

    copyPropFilesRemotely()

        # install the new build

    install()


        # Verify if Node-Manager GUI is accessible

    verifyNMGuiAccess()


        # Cleaning-up ssh connections

    cleanUpSsh()

    scriptEndTS = time.time()
    print '\nScript started at: ' + getTimeStamp(scriptStartTS)
    print 'Script stopped at: ' + getTimeStamp(scriptEndTS)
    timeDiff = int(scriptEndTS - scriptStartTS)
    print 'Total time taken : ' + str(int(timeDiff / 60)) \
        + ' minutes & ' + str(int(timeDiff % 60)) + ' seconds!'

