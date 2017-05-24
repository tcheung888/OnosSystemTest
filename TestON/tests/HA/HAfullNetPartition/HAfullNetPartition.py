"""
Description: This test is to determine if ONOS can handle
             a full network partion

List of test cases:
CASE1: Compile ONOS and push it to the test machines
CASE2: Assign devices to controllers
CASE21: Assign mastership to controllers
CASE3: Assign intents
CASE4: Ping across added host intents
CASE5: Reading state of ONOS
CASE61: The Failure inducing case.
CASE62: The Failure recovery case.
CASE7: Check state after control plane failure
CASE8: Compare topo
CASE9: Link s3-s28 down
CASE10: Link s3-s28 up
CASE11: Switch down
CASE12: Switch up
CASE13: Clean up
CASE14: start election app on all onos nodes
CASE15: Check that Leadership Election is still functional
CASE16: Install Distributed Primitives app
CASE17: Check for basic functionality with distributed primitives
"""
class HAfullNetPartition:

    def __init__( self ):
        self.default = ''

    def CASE1( self, main ):
        """
        CASE1 is to compile ONOS and push it to the test machines

        Startup sequence:
        cell <name>
        onos-verify-cell
        NOTE: temporary - onos-remove-raft-logs
        onos-uninstall
        start mininet
        git pull
        mvn clean install
        onos-package
        onos-install -f
        onos-wait-for-start
        start cli sessions
        start tcpdump
        """
        import imp
        import pexpect
        import time
        import json
        main.log.info( "ONOS HA test: Partition ONOS nodes into two sub-clusters - " +
                         "initialization" )
        main.case( "Setting up test environment" )
        main.caseExplanation = "Setup the test environment including " +\
                                "installing ONOS, starting Mininet and ONOS" +\
                                "cli sessions."

        # load some variables from the params file
        PULLCODE = False
        if main.params[ 'Git' ] == 'True':
            PULLCODE = True
        gitBranch = main.params[ 'branch' ]
        cellName = main.params[ 'ENV' ][ 'cellName' ]

        main.numCtrls = int( main.params[ 'num_controllers' ] )
        if main.ONOSbench.maxNodes:
            if main.ONOSbench.maxNodes < main.numCtrls:
                main.numCtrls = int( main.ONOSbench.maxNodes )
        # set global variables
        global ONOS1Port
        global ONOS2Port
        global ONOS3Port
        global ONOS4Port
        global ONOS5Port
        global ONOS6Port
        global ONOS7Port
        # These are for csv plotting in jenkins
        global labels
        global data
        labels = []
        data = []

        # FIXME: just get controller port from params?
        # TODO: do we really need all these?
        ONOS1Port = main.params[ 'CTRL' ][ 'port1' ]
        ONOS2Port = main.params[ 'CTRL' ][ 'port2' ]
        ONOS3Port = main.params[ 'CTRL' ][ 'port3' ]
        ONOS4Port = main.params[ 'CTRL' ][ 'port4' ]
        ONOS5Port = main.params[ 'CTRL' ][ 'port5' ]
        ONOS6Port = main.params[ 'CTRL' ][ 'port6' ]
        ONOS7Port = main.params[ 'CTRL' ][ 'port7' ]

        try:
            from tests.HA.dependencies.HA import HA
            main.HA = HA()
        except Exception as e:
            main.log.exception( e )
            main.cleanup()
            main.exit()

        main.CLIs = []
        main.nodes = []
        ipList = []
        for i in range( 1, main.numCtrls + 1 ):
            try:
                main.CLIs.append( getattr( main, 'ONOScli' + str( i ) ) )
                main.nodes.append( getattr( main, 'ONOS' + str( i ) ) )
                ipList.append( main.nodes[ -1 ].ip_address )
            except AttributeError:
                break

        main.step( "Create cell file" )
        cellAppString = main.params[ 'ENV' ][ 'appString' ]
        main.ONOSbench.createCellFile( main.ONOSbench.ip_address, cellName,
                                       main.Mininet1.ip_address,
                                       cellAppString, ipList )
        main.step( "Applying cell variable to environment" )
        cellResult = main.ONOSbench.setCell( cellName )
        verifyResult = main.ONOSbench.verifyCell()

        # FIXME:this is short term fix
        main.log.info( "Removing raft logs" )
        main.ONOSbench.onosRemoveRaftLogs()

        main.log.info( "Uninstalling ONOS" )
        for node in main.nodes:
            main.ONOSbench.onosUninstall( node.ip_address )

        # Make sure ONOS is DEAD
        main.log.info( "Killing any ONOS processes" )
        killResults = main.TRUE
        for node in main.nodes:
            killed = main.ONOSbench.onosKill( node.ip_address )
            killResults = killResults and killed

        cleanInstallResult = main.TRUE
        gitPullResult = main.TRUE

        main.step( "Starting Mininet" )
        # scp topo file to mininet
        # TODO: move to params?
        topoName = "obelisk.py"
        filePath = main.ONOSbench.home + "/tools/test/topos/"
        main.ONOSbench.scp( main.Mininet1,
                            filePath + topoName,
                            main.Mininet1.home,
                            direction="to" )
        mnResult = main.Mininet1.startNet()
        utilities.assert_equals( expect=main.TRUE, actual=mnResult,
                                 onpass="Mininet Started",
                                 onfail="Error starting Mininet" )

        main.step( "Git checkout and pull " + gitBranch )
        if PULLCODE:
            main.ONOSbench.gitCheckout( gitBranch )
            gitPullResult = main.ONOSbench.gitPull()
            # values of 1 or 3 are good
            utilities.assert_lesser( expect=0, actual=gitPullResult,
                                      onpass="Git pull successful",
                                      onfail="Git pull failed" )
        main.ONOSbench.getVersion( report=True )

        main.step( "Using mvn clean install" )
        cleanInstallResult = main.TRUE
        if PULLCODE and gitPullResult == main.TRUE:
            cleanInstallResult = main.ONOSbench.cleanInstall()
        else:
            main.log.warn( "Did not pull new code so skipping mvn " +
                           "clean install" )
        utilities.assert_equals( expect=main.TRUE,
                                 actual=cleanInstallResult,
                                 onpass="MCI successful",
                                 onfail="MCI failed" )
        # GRAPHS
        # NOTE: important params here:
        #       job = name of Jenkins job
        #       Plot Name = Plot-HA, only can be used if multiple plots
        #       index = The number of the graph under plot name
        job = "HAfullNetPartition"
        plotName = "Plot-HA"
        index = "2"
        graphs = '<ac:structured-macro ac:name="html">\n'
        graphs += '<ac:plain-text-body><![CDATA[\n'
        graphs += '<iframe src="https://onos-jenkins.onlab.us/job/' + job +\
                  '/plot/' + plotName + '/getPlot?index=' + index +\
                  '&width=500&height=300"' +\
                  'noborder="0" width="500" height="300" scrolling="yes" ' +\
                  'seamless="seamless"></iframe>\n'
        graphs += ']]></ac:plain-text-body>\n'
        graphs += '</ac:structured-macro>\n'
        main.log.wiki( graphs )

        main.step( "Creating ONOS package" )
        # copy gen-partions file to ONOS
        # NOTE: this assumes TestON and ONOS are on the same machine
        srcFile = main.testDir + "/HA/dependencies/onos-gen-partitions"
        dstDir = main.ONOSbench.home + "/tools/test/bin/onos-gen-partitions"
        cpResult = main.ONOSbench.secureCopy( main.ONOSbench.user_name,
                                              main.ONOSbench.ip_address,
                                              srcFile,
                                              dstDir,
                                              pwd=main.ONOSbench.pwd,
                                              direction="from" )
        packageResult = main.ONOSbench.buckBuild()
        utilities.assert_equals( expect=main.TRUE, actual=packageResult,
                                 onpass="ONOS package successful",
                                 onfail="ONOS package failed" )

        main.step( "Installing ONOS package" )
        onosInstallResult = main.TRUE
        for node in main.nodes:
            tmpResult = main.ONOSbench.onosInstall( options="-f",
                                                    node=node.ip_address )
            onosInstallResult = onosInstallResult and tmpResult
        utilities.assert_equals( expect=main.TRUE, actual=onosInstallResult,
                                 onpass="ONOS install successful",
                                 onfail="ONOS install failed" )
        # clean up gen-partitions file
        try:
            main.ONOSbench.handle.sendline( "cd " + main.ONOSbench.home )
            main.ONOSbench.handle.expect( main.ONOSbench.home + "\$" )
            main.ONOSbench.handle.sendline( "git checkout -- tools/test/bin/onos-gen-partitions" )
            main.ONOSbench.handle.expect( main.ONOSbench.home + "\$" )
            main.log.info( " Cleaning custom gen partitions file, response was: \n" +
                           str( main.ONOSbench.handle.before ) )
        except ( pexpect.TIMEOUT, pexpect.EOF ):
            main.log.exception( "ONOSbench: pexpect exception found:" +
                                main.ONOSbench.handle.before )
            main.cleanup()
            main.exit()

        main.step( "Set up ONOS secure SSH" )
        secureSshResult = main.TRUE
        for node in main.nodes:
            secureSshResult = secureSshResult and main.ONOSbench.onosSecureSSH( node=node.ip_address )
        utilities.assert_equals( expect=main.TRUE, actual=secureSshResult,
                                 onpass="Test step PASS",
                                 onfail="Test step FAIL" )

        main.step( "Checking if ONOS is up yet" )
        for i in range( 2 ):
            onosIsupResult = main.TRUE
            for node in main.nodes:
                started = main.ONOSbench.isup( node.ip_address )
                if not started:
                    main.log.error( node.name + " hasn't started" )
                onosIsupResult = onosIsupResult and started
            if onosIsupResult == main.TRUE:
                break
        utilities.assert_equals( expect=main.TRUE, actual=onosIsupResult,
                                 onpass="ONOS startup successful",
                                 onfail="ONOS startup failed" )

        main.step( "Starting ONOS CLI sessions" )
        cliResults = main.TRUE
        threads = []
        for i in range( main.numCtrls ):
            t = main.Thread( target=main.CLIs[ i ].startOnosCli,
                             name="startOnosCli-" + str( i ),
                             args=[ main.nodes[ i ].ip_address ] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            cliResults = cliResults and t.result
        utilities.assert_equals( expect=main.TRUE, actual=cliResults,
                                 onpass="ONOS cli startup successful",
                                 onfail="ONOS cli startup failed" )

        # Create a list of active nodes for use when some nodes are stopped
        main.activeNodes = [ i for i in range( 0, len( main.CLIs ) ) ]

        if main.params[ 'tcpdump' ].lower() == "true":
            main.step( "Start Packet Capture MN" )
            main.Mininet2.startTcpdump(
                str( main.params[ 'MNtcpdump' ][ 'folder' ] ) + str( main.TEST )
                + "-MN.pcap",
                intf=main.params[ 'MNtcpdump' ][ 'intf' ],
                port=main.params[ 'MNtcpdump' ][ 'port' ] )

        main.step( "Checking ONOS nodes" )
        nodeResults = utilities.retry( main.HA.nodesCheck,
                                       False,
                                       args=[ main.activeNodes ],
                                       attempts=5 )

        utilities.assert_equals( expect=True, actual=nodeResults,
                                 onpass="Nodes check successful",
                                 onfail="Nodes check NOT successful" )

        if not nodeResults:
            for i in main.activeNodes:
                cli = main.CLIs[ i ]
                main.log.debug( "{} components not ACTIVE: \n{}".format(
                    cli.name,
                    cli.sendline( "scr:list | grep -v ACTIVE" ) ) )
            main.log.error( "Failed to start ONOS, stopping test" )
            main.cleanup()
            main.exit()

        main.step( "Activate apps defined in the params file" )
        # get data from the params
        apps = main.params.get( 'apps' )
        if apps:
            apps = apps.split( ',' )
            main.log.warn( apps )
            activateResult = True
            for app in apps:
                main.CLIs[ 0 ].app( app, "Activate" )
            # TODO: check this worked
            time.sleep( 10 )  # wait for apps to activate
            for app in apps:
                state = main.CLIs[ 0 ].appStatus( app )
                if state == "ACTIVE":
                    activateResult = activateResult and True
                else:
                    main.log.error( "{} is in {} state".format( app, state ) )
                    activateResult = False
            utilities.assert_equals( expect=True,
                                     actual=activateResult,
                                     onpass="Successfully activated apps",
                                     onfail="Failed to activate apps" )
        else:
            main.log.warn( "No apps were specified to be loaded after startup" )

        main.step( "Set ONOS configurations" )
        config = main.params.get( 'ONOS_Configuration' )
        if config:
            main.log.debug( config )
            checkResult = main.TRUE
            for component in config:
                for setting in config[ component ]:
                    value = config[ component ][ setting ]
                    check = main.CLIs[ 0 ].setCfg( component, setting, value )
                    main.log.info( "Value was changed? {}".format( main.TRUE == check ) )
                    checkResult = check and checkResult
            utilities.assert_equals( expect=main.TRUE,
                                     actual=checkResult,
                                     onpass="Successfully set config",
                                     onfail="Failed to set config" )
        else:
            main.log.warn( "No configurations were specified to be changed after startup" )

        main.step( "App Ids check" )
        appCheck = main.TRUE
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].appToIDCheck,
                             name="appToIDCheck-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            appCheck = appCheck and t.result
        if appCheck != main.TRUE:
            node = main.activeNodes[ 0 ]
            main.log.warn( main.CLIs[ node ].apps() )
            main.log.warn( main.CLIs[ node ].appIDs() )
        utilities.assert_equals( expect=main.TRUE, actual=appCheck,
                                 onpass="App Ids seem to be correct",
                                 onfail="Something is wrong with app Ids" )

    def CASE2( self, main ):
        """
        Assign devices to controllers
        """
        import re
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        assert ONOS1Port, "ONOS1Port not defined"
        assert ONOS2Port, "ONOS2Port not defined"
        assert ONOS3Port, "ONOS3Port not defined"
        assert ONOS4Port, "ONOS4Port not defined"
        assert ONOS5Port, "ONOS5Port not defined"
        assert ONOS6Port, "ONOS6Port not defined"
        assert ONOS7Port, "ONOS7Port not defined"

        main.case( "Assigning devices to controllers" )
        main.caseExplanation = "Assign switches to ONOS using 'ovs-vsctl' " +\
                                "and check that an ONOS node becomes the " +\
                                "master of the device."
        main.step( "Assign switches to controllers" )

        ipList = []
        for i in range( main.numCtrls ):
            ipList.append( main.nodes[ i ].ip_address )
        swList = []
        for i in range( 1, 29 ):
            swList.append( "s" + str( i ) )
        main.Mininet1.assignSwController( sw=swList, ip=ipList )

        mastershipCheck = main.TRUE
        for i in range( 1, 29 ):
            response = main.Mininet1.getSwController( "s" + str( i ) )
            try:
                main.log.info( str( response ) )
            except Exception:
                main.log.info( repr( response ) )
            for node in main.nodes:
                if re.search( "tcp:" + node.ip_address, response ):
                    mastershipCheck = mastershipCheck and main.TRUE
                else:
                    main.log.error( "Error, node " + node.ip_address + " is " +
                                    "not in the list of controllers s" +
                                    str( i ) + " is connecting to." )
                    mastershipCheck = main.FALSE
        utilities.assert_equals(
            expect=main.TRUE,
            actual=mastershipCheck,
            onpass="Switch mastership assigned correctly",
            onfail="Switches not assigned correctly to controllers" )

    def CASE21( self, main ):
        """
        Assign mastership to controllers
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        assert ONOS1Port, "ONOS1Port not defined"
        assert ONOS2Port, "ONOS2Port not defined"
        assert ONOS3Port, "ONOS3Port not defined"
        assert ONOS4Port, "ONOS4Port not defined"
        assert ONOS5Port, "ONOS5Port not defined"
        assert ONOS6Port, "ONOS6Port not defined"
        assert ONOS7Port, "ONOS7Port not defined"

        main.case( "Assigning Controller roles for switches" )
        main.caseExplanation = "Check that ONOS is connected to each " +\
                                "device. Then manually assign" +\
                                " mastership to specific ONOS nodes using" +\
                                " 'device-role'"
        main.step( "Assign mastership of switches to specific controllers" )
        # Manually assign mastership to the controller we want
        roleCall = main.TRUE

        ipList = []
        deviceList = []
        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        try:
            # Assign mastership to specific controllers. This assignment was
            # determined for a 7 node cluser, but will work with any sized
            # cluster
            for i in range( 1, 29 ):  # switches 1 through 28
                # set up correct variables:
                if i == 1:
                    c = 0
                    ip = main.nodes[ c ].ip_address  # ONOS1
                    deviceId = onosCli.getDevice( "1000" ).get( 'id' )
                elif i == 2:
                    c = 1 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS2
                    deviceId = onosCli.getDevice( "2000" ).get( 'id' )
                elif i == 3:
                    c = 1 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS2
                    deviceId = onosCli.getDevice( "3000" ).get( 'id' )
                elif i == 4:
                    c = 3 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS4
                    deviceId = onosCli.getDevice( "3004" ).get( 'id' )
                elif i == 5:
                    c = 2 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS3
                    deviceId = onosCli.getDevice( "5000" ).get( 'id' )
                elif i == 6:
                    c = 2 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS3
                    deviceId = onosCli.getDevice( "6000" ).get( 'id' )
                elif i == 7:
                    c = 5 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS6
                    deviceId = onosCli.getDevice( "6007" ).get( 'id' )
                elif i >= 8 and i <= 17:
                    c = 4 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS5
                    dpid = '3' + str( i ).zfill( 3 )
                    deviceId = onosCli.getDevice( dpid ).get( 'id' )
                elif i >= 18 and i <= 27:
                    c = 6 % main.numCtrls
                    ip = main.nodes[ c ].ip_address  # ONOS7
                    dpid = '6' + str( i ).zfill( 3 )
                    deviceId = onosCli.getDevice( dpid ).get( 'id' )
                elif i == 28:
                    c = 0
                    ip = main.nodes[ c ].ip_address  # ONOS1
                    deviceId = onosCli.getDevice( "2800" ).get( 'id' )
                else:
                    main.log.error( "You didn't write an else statement for " +
                                    "switch s" + str( i ) )
                    roleCall = main.FALSE
                # Assign switch
                assert deviceId, "No device id for s" + str( i ) + " in ONOS"
                # TODO: make this controller dynamic
                roleCall = roleCall and onosCli.deviceRole( deviceId, ip )
                ipList.append( ip )
                deviceList.append( deviceId )
        except ( AttributeError, AssertionError ):
            main.log.exception( "Something is wrong with ONOS device view" )
            main.log.info( onosCli.devices() )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=roleCall,
            onpass="Re-assigned switch mastership to designated controller",
            onfail="Something wrong with deviceRole calls" )

        main.step( "Check mastership was correctly assigned" )
        roleCheck = main.TRUE
        # NOTE: This is due to the fact that device mastership change is not
        #       atomic and is actually a multi step process
        time.sleep( 5 )
        for i in range( len( ipList ) ):
            ip = ipList[ i ]
            deviceId = deviceList[ i ]
            # Check assignment
            master = onosCli.getRole( deviceId ).get( 'master' )
            if ip in master:
                roleCheck = roleCheck and main.TRUE
            else:
                roleCheck = roleCheck and main.FALSE
                main.log.error( "Error, controller " + ip + " is not" +
                                " master " + "of device " +
                                str( deviceId ) + ". Master is " +
                                repr( master ) + "." )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=roleCheck,
            onpass="Switches were successfully reassigned to designated " +
                   "controller",
            onfail="Switches were not successfully reassigned" )

    def CASE3( self, main ):
        """
        Assign intents
        """
        import time
        import json
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        main.case( "Adding host Intents" )
        main.caseExplanation = "Discover hosts by using pingall then " +\
                                "assign predetermined host-to-host intents." +\
                                " After installation, check that the intent" +\
                                " is distributed to all nodes and the state" +\
                                " is INSTALLED"

        # install onos-app-fwd
        main.step( "Install reactive forwarding app" )
        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        installResults = onosCli.activateApp( "org.onosproject.fwd" )
        utilities.assert_equals( expect=main.TRUE, actual=installResults,
                                 onpass="Install fwd successful",
                                 onfail="Install fwd failed" )

        main.step( "Check app ids" )
        appCheck = main.TRUE
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].appToIDCheck,
                             name="appToIDCheck-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            appCheck = appCheck and t.result
        if appCheck != main.TRUE:
            main.log.warn( onosCli.apps() )
            main.log.warn( onosCli.appIDs() )
        utilities.assert_equals( expect=main.TRUE, actual=appCheck,
                                 onpass="App Ids seem to be correct",
                                 onfail="Something is wrong with app Ids" )

        main.step( "Discovering Hosts( Via pingall for now )" )
        # FIXME: Once we have a host discovery mechanism, use that instead
        # REACTIVE FWD test
        pingResult = main.FALSE
        passMsg = "Reactive Pingall test passed"
        time1 = time.time()
        pingResult = main.Mininet1.pingall()
        time2 = time.time()
        if not pingResult:
            main.log.warn( "First pingall failed. Trying again..." )
            pingResult = main.Mininet1.pingall()
            passMsg += " on the second try"
        utilities.assert_equals(
            expect=main.TRUE,
            actual=pingResult,
            onpass=passMsg,
            onfail="Reactive Pingall failed, " +
                   "one or more ping pairs failed" )
        main.log.info( "Time for pingall: %2f seconds" %
                       ( time2 - time1 ) )
        # timeout for fwd flows
        time.sleep( 11 )
        # uninstall onos-app-fwd
        main.step( "Uninstall reactive forwarding app" )
        node = main.activeNodes[ 0 ]
        uninstallResult = main.CLIs[ node ].deactivateApp( "org.onosproject.fwd" )
        utilities.assert_equals( expect=main.TRUE, actual=uninstallResult,
                                 onpass="Uninstall fwd successful",
                                 onfail="Uninstall fwd failed" )

        main.step( "Check app ids" )
        threads = []
        appCheck2 = main.TRUE
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].appToIDCheck,
                             name="appToIDCheck-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            appCheck2 = appCheck2 and t.result
        if appCheck2 != main.TRUE:
            node = main.activeNodes[ 0 ]
            main.log.warn( main.CLIs[ node ].apps() )
            main.log.warn( main.CLIs[ node ].appIDs() )
        utilities.assert_equals( expect=main.TRUE, actual=appCheck2,
                                 onpass="App Ids seem to be correct",
                                 onfail="Something is wrong with app Ids" )

        main.step( "Add host intents via cli" )
        intentIds = []
        # TODO: move the host numbers to params
        #       Maybe look at all the paths we ping?
        intentAddResult = True
        hostResult = main.TRUE
        for i in range( 8, 18 ):
            main.log.info( "Adding host intent between h" + str( i ) +
                           " and h" + str( i + 10 ) )
            host1 = "00:00:00:00:00:" + \
                str( hex( i )[ 2: ] ).zfill( 2 ).upper()
            host2 = "00:00:00:00:00:" + \
                str( hex( i + 10 )[ 2: ] ).zfill( 2 ).upper()
            # NOTE: getHost can return None
            host1Dict = onosCli.getHost( host1 )
            host2Dict = onosCli.getHost( host2 )
            host1Id = None
            host2Id = None
            if host1Dict and host2Dict:
                host1Id = host1Dict.get( 'id', None )
                host2Id = host2Dict.get( 'id', None )
            if host1Id and host2Id:
                nodeNum = ( i % len( main.activeNodes ) )
                node = main.activeNodes[ nodeNum ]
                tmpId = main.CLIs[ node ].addHostIntent( host1Id, host2Id )
                if tmpId:
                    main.log.info( "Added intent with id: " + tmpId )
                    intentIds.append( tmpId )
                else:
                    main.log.error( "addHostIntent returned: " +
                                     repr( tmpId ) )
            else:
                main.log.error( "Error, getHost() failed for h" + str( i ) +
                                " and/or h" + str( i + 10 ) )
                node = main.activeNodes[ 0 ]
                hosts = main.CLIs[ node ].hosts()
                main.log.warn( "Hosts output: " )
                try:
                    main.log.warn( json.dumps( json.loads( hosts ),
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                except ( ValueError, TypeError ):
                    main.log.warn( repr( hosts ) )
                hostResult = main.FALSE
        utilities.assert_equals( expect=main.TRUE, actual=hostResult,
                                 onpass="Found a host id for each host",
                                 onfail="Error looking up host ids" )

        intentStart = time.time()
        onosIds = onosCli.getAllIntentsId()
        main.log.info( "Submitted intents: " + str( intentIds ) )
        main.log.info( "Intents in ONOS: " + str( onosIds ) )
        for intent in intentIds:
            if intent in onosIds:
                pass  # intent submitted is in onos
            else:
                intentAddResult = False
        if intentAddResult:
            intentStop = time.time()
        else:
            intentStop = None
        # Print the intent states
        intents = onosCli.intents()
        intentStates = []
        installedCheck = True
        main.log.info( "%-6s%-15s%-15s" % ( 'Count', 'ID', 'State' ) )
        count = 0
        try:
            for intent in json.loads( intents ):
                state = intent.get( 'state', None )
                if "INSTALLED" not in state:
                    installedCheck = False
                intentId = intent.get( 'id', None )
                intentStates.append( ( intentId, state ) )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing intents" )
        # add submitted intents not in the store
        tmplist = [ i for i, s in intentStates ]
        missingIntents = False
        for i in intentIds:
            if i not in tmplist:
                intentStates.append( ( i, " - " ) )
                missingIntents = True
        intentStates.sort()
        for i, s in intentStates:
            count += 1
            main.log.info( "%-6s%-15s%-15s" %
                           ( str( count ), str( i ), str( s ) ) )
        leaders = onosCli.leaders()
        try:
            missing = False
            if leaders:
                parsedLeaders = json.loads( leaders )
                main.log.warn( json.dumps( parsedLeaders,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # check for all intent partitions
                topics = []
                for i in range( 14 ):
                    topics.append( "work-partition-" + str( i ) )
                main.log.debug( topics )
                ONOStopics = [ j[ 'topic' ] for j in parsedLeaders ]
                for topic in topics:
                    if topic not in ONOStopics:
                        main.log.error( "Error: " + topic +
                                        " not in leaders" )
                        missing = True
            else:
                main.log.error( "leaders() returned None" )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing leaders" )
            main.log.error( repr( leaders ) )
        # Check all nodes
        if missing:
            for i in main.activeNodes:
                response = main.CLIs[ i ].leaders( jsonFormat=False )
                main.log.warn( str( main.CLIs[ i ].name ) + " leaders output: \n" +
                               str( response ) )

        partitions = onosCli.partitions()
        try:
            if partitions:
                parsedPartitions = json.loads( partitions )
                main.log.warn( json.dumps( parsedPartitions,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # TODO check for a leader in all paritions
                # TODO check for consistency among nodes
            else:
                main.log.error( "partitions() returned None" )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing partitions" )
            main.log.error( repr( partitions ) )
        pendingMap = onosCli.pendingMap()
        try:
            if pendingMap:
                parsedPending = json.loads( pendingMap )
                main.log.warn( json.dumps( parsedPending,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # TODO check something here?
            else:
                main.log.error( "pendingMap() returned None" )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing pending map" )
            main.log.error( repr( pendingMap ) )

        intentAddResult = bool( intentAddResult and not missingIntents and
                                installedCheck )
        if not intentAddResult:
            main.log.error( "Error in pushing host intents to ONOS" )

        main.step( "Intent Anti-Entropy dispersion" )
        for j in range( 100 ):
            correct = True
            main.log.info( "Submitted intents: " + str( sorted( intentIds ) ) )
            for i in main.activeNodes:
                onosIds = []
                ids = main.CLIs[ i ].getAllIntentsId()
                onosIds.append( ids )
                main.log.debug( "Intents in " + main.CLIs[ i ].name + ": " +
                                str( sorted( onosIds ) ) )
                if sorted( ids ) != sorted( intentIds ):
                    main.log.warn( "Set of intent IDs doesn't match" )
                    correct = False
                    break
                else:
                    intents = json.loads( main.CLIs[ i ].intents() )
                    for intent in intents:
                        if intent[ 'state' ] != "INSTALLED":
                            main.log.warn( "Intent " + intent[ 'id' ] +
                                           " is " + intent[ 'state' ] )
                            correct = False
                            break
            if correct:
                break
            else:
                time.sleep( 1 )
        if not intentStop:
            intentStop = time.time()
        global gossipTime
        gossipTime = intentStop - intentStart
        main.log.info( "It took about " + str( gossipTime ) +
                        " seconds for all intents to appear in each node" )
        gossipPeriod = int( main.params[ 'timers' ][ 'gossip' ] )
        maxGossipTime = gossipPeriod * len( main.activeNodes )
        utilities.assert_greater_equals(
                expect=maxGossipTime, actual=gossipTime,
                onpass="ECM anti-entropy for intents worked within " +
                       "expected time",
                onfail="Intent ECM anti-entropy took too long. " +
                       "Expected time:{}, Actual time:{}".format( maxGossipTime,
                                                                  gossipTime ) )
        if gossipTime <= maxGossipTime:
            intentAddResult = True

        if not intentAddResult or "key" in pendingMap:
            import time
            installedCheck = True
            main.log.info( "Sleeping 60 seconds to see if intents are found" )
            time.sleep( 60 )
            onosIds = onosCli.getAllIntentsId()
            main.log.info( "Submitted intents: " + str( intentIds ) )
            main.log.info( "Intents in ONOS: " + str( onosIds ) )
            # Print the intent states
            intents = onosCli.intents()
            intentStates = []
            main.log.info( "%-6s%-15s%-15s" % ( 'Count', 'ID', 'State' ) )
            count = 0
            try:
                for intent in json.loads( intents ):
                    # Iter through intents of a node
                    state = intent.get( 'state', None )
                    if "INSTALLED" not in state:
                        installedCheck = False
                    intentId = intent.get( 'id', None )
                    intentStates.append( ( intentId, state ) )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing intents" )
            # add submitted intents not in the store
            tmplist = [ i for i, s in intentStates ]
            for i in intentIds:
                if i not in tmplist:
                    intentStates.append( ( i, " - " ) )
            intentStates.sort()
            for i, s in intentStates:
                count += 1
                main.log.info( "%-6s%-15s%-15s" %
                               ( str( count ), str( i ), str( s ) ) )
            leaders = onosCli.leaders()
            try:
                missing = False
                if leaders:
                    parsedLeaders = json.loads( leaders )
                    main.log.warn( json.dumps( parsedLeaders,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # check for all intent partitions
                    # check for election
                    topics = []
                    for i in range( 14 ):
                        topics.append( "work-partition-" + str( i ) )
                    # FIXME: this should only be after we start the app
                    topics.append( "org.onosproject.election" )
                    main.log.debug( topics )
                    ONOStopics = [ j[ 'topic' ] for j in parsedLeaders ]
                    for topic in topics:
                        if topic not in ONOStopics:
                            main.log.error( "Error: " + topic +
                                            " not in leaders" )
                            missing = True
                else:
                    main.log.error( "leaders() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing leaders" )
                main.log.error( repr( leaders ) )
            # Check all nodes
            if missing:
                for i in main.activeNodes:
                    node = main.CLIs[ i ]
                    response = node.leaders( jsonFormat=False )
                    main.log.warn( str( node.name ) + " leaders output: \n" +
                                   str( response ) )

            partitions = onosCli.partitions()
            try:
                if partitions:
                    parsedPartitions = json.loads( partitions )
                    main.log.warn( json.dumps( parsedPartitions,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # TODO check for a leader in all paritions
                    # TODO check for consistency among nodes
                else:
                    main.log.error( "partitions() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing partitions" )
                main.log.error( repr( partitions ) )
            pendingMap = onosCli.pendingMap()
            try:
                if pendingMap:
                    parsedPending = json.loads( pendingMap )
                    main.log.warn( json.dumps( parsedPending,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # TODO check something here?
                else:
                    main.log.error( "pendingMap() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing pending map" )
                main.log.error( repr( pendingMap ) )

    def CASE4( self, main ):
        """
        Ping across added host intents
        """
        import json
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        main.case( "Verify connectivity by sending traffic across Intents" )
        main.caseExplanation = "Ping across added host intents to check " +\
                                "functionality and check the state of " +\
                                "the intent"

        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        main.step( "Check Intent state" )
        installedCheck = False
        loopCount = 0
        while not installedCheck and loopCount < 40:
            installedCheck = True
            # Print the intent states
            intents = onosCli.intents()
            intentStates = []
            main.log.info( "%-6s%-15s%-15s" % ( 'Count', 'ID', 'State' ) )
            count = 0
            # Iter through intents of a node
            try:
                for intent in json.loads( intents ):
                    state = intent.get( 'state', None )
                    if "INSTALLED" not in state:
                        installedCheck = False
                    intentId = intent.get( 'id', None )
                    intentStates.append( ( intentId, state ) )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing intents." )
            # Print states
            intentStates.sort()
            for i, s in intentStates:
                count += 1
                main.log.info( "%-6s%-15s%-15s" %
                               ( str( count ), str( i ), str( s ) ) )
            if not installedCheck:
                time.sleep( 1 )
                loopCount += 1
        utilities.assert_equals( expect=True, actual=installedCheck,
                                 onpass="Intents are all INSTALLED",
                                 onfail="Intents are not all in " +
                                        "INSTALLED state" )

        main.step( "Ping across added host intents" )
        PingResult = main.TRUE
        for i in range( 8, 18 ):
            ping = main.Mininet1.pingHost( src="h" + str( i ),
                                           target="h" + str( i + 10 ) )
            PingResult = PingResult and ping
            if ping == main.FALSE:
                main.log.warn( "Ping failed between h" + str( i ) +
                               " and h" + str( i + 10 ) )
            elif ping == main.TRUE:
                main.log.info( "Ping test passed!" )
                # Don't set PingResult or you'd override failures
        if PingResult == main.FALSE:
            main.log.error(
                "Intents have not been installed correctly, pings failed." )
            # TODO: pretty print
            main.log.warn( "ONOS1 intents: " )
            try:
                tmpIntents = onosCli.intents()
                main.log.warn( json.dumps( json.loads( tmpIntents ),
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
            except ( ValueError, TypeError ):
                main.log.warn( repr( tmpIntents ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=PingResult,
            onpass="Intents have been installed correctly and pings work",
            onfail="Intents have not been installed correctly, pings failed." )

        main.step( "Check leadership of topics" )
        leaders = onosCli.leaders()
        topicCheck = main.TRUE
        try:
            if leaders:
                parsedLeaders = json.loads( leaders )
                main.log.warn( json.dumps( parsedLeaders,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # check for all intent partitions
                # check for election
                # TODO: Look at Devices as topics now that it uses this system
                topics = []
                for i in range( 14 ):
                    topics.append( "work-partition-" + str( i ) )
                # FIXME: this should only be after we start the app
                # FIXME: topics.append( "org.onosproject.election" )
                # Print leaders output
                main.log.debug( topics )
                ONOStopics = [ j[ 'topic' ] for j in parsedLeaders ]
                for topic in topics:
                    if topic not in ONOStopics:
                        main.log.error( "Error: " + topic +
                                        " not in leaders" )
                        topicCheck = main.FALSE
            else:
                main.log.error( "leaders() returned None" )
                topicCheck = main.FALSE
        except ( ValueError, TypeError ):
            topicCheck = main.FALSE
            main.log.exception( "Error parsing leaders" )
            main.log.error( repr( leaders ) )
            # TODO: Check for a leader of these topics
        # Check all nodes
        if topicCheck:
            for i in main.activeNodes:
                node = main.CLIs[ i ]
                response = node.leaders( jsonFormat=False )
                main.log.warn( str( node.name ) + " leaders output: \n" +
                               str( response ) )

        utilities.assert_equals( expect=main.TRUE, actual=topicCheck,
                                 onpass="intent Partitions is in leaders",
                                 onfail="Some topics were lost " )
        # Print partitions
        partitions = onosCli.partitions()
        try:
            if partitions:
                parsedPartitions = json.loads( partitions )
                main.log.warn( json.dumps( parsedPartitions,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # TODO check for a leader in all paritions
                # TODO check for consistency among nodes
            else:
                main.log.error( "partitions() returned None" )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing partitions" )
            main.log.error( repr( partitions ) )
        # Print Pending Map
        pendingMap = onosCli.pendingMap()
        try:
            if pendingMap:
                parsedPending = json.loads( pendingMap )
                main.log.warn( json.dumps( parsedPending,
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
                # TODO check something here?
            else:
                main.log.error( "pendingMap() returned None" )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing pending map" )
            main.log.error( repr( pendingMap ) )

        if not installedCheck:
            main.log.info( "Waiting 60 seconds to see if the state of " +
                           "intents change" )
            time.sleep( 60 )
            # Print the intent states
            intents = onosCli.intents()
            intentStates = []
            main.log.info( "%-6s%-15s%-15s" % ( 'Count', 'ID', 'State' ) )
            count = 0
            # Iter through intents of a node
            try:
                for intent in json.loads( intents ):
                    state = intent.get( 'state', None )
                    if "INSTALLED" not in state:
                        installedCheck = False
                    intentId = intent.get( 'id', None )
                    intentStates.append( ( intentId, state ) )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing intents." )
            intentStates.sort()
            for i, s in intentStates:
                count += 1
                main.log.info( "%-6s%-15s%-15s" %
                               ( str( count ), str( i ), str( s ) ) )
            leaders = onosCli.leaders()
            try:
                missing = False
                if leaders:
                    parsedLeaders = json.loads( leaders )
                    main.log.warn( json.dumps( parsedLeaders,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # check for all intent partitions
                    # check for election
                    topics = []
                    for i in range( 14 ):
                        topics.append( "work-partition-" + str( i ) )
                    # FIXME: this should only be after we start the app
                    topics.append( "org.onosproject.election" )
                    main.log.debug( topics )
                    ONOStopics = [ j[ 'topic' ] for j in parsedLeaders ]
                    for topic in topics:
                        if topic not in ONOStopics:
                            main.log.error( "Error: " + topic +
                                            " not in leaders" )
                            missing = True
                else:
                    main.log.error( "leaders() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing leaders" )
                main.log.error( repr( leaders ) )
            if missing:
                for i in main.activeNodes:
                    node = main.CLIs[ i ]
                    response = node.leaders( jsonFormat=False )
                    main.log.warn( str( node.name ) + " leaders output: \n" +
                                   str( response ) )

            partitions = onosCli.partitions()
            try:
                if partitions:
                    parsedPartitions = json.loads( partitions )
                    main.log.warn( json.dumps( parsedPartitions,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # TODO check for a leader in all paritions
                    # TODO check for consistency among nodes
                else:
                    main.log.error( "partitions() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing partitions" )
                main.log.error( repr( partitions ) )
            pendingMap = onosCli.pendingMap()
            try:
                if pendingMap:
                    parsedPending = json.loads( pendingMap )
                    main.log.warn( json.dumps( parsedPending,
                                               sort_keys=True,
                                               indent=4,
                                               separators=( ',', ': ' ) ) )
                    # TODO check something here?
                else:
                    main.log.error( "pendingMap() returned None" )
            except ( ValueError, TypeError ):
                main.log.exception( "Error parsing pending map" )
                main.log.error( repr( pendingMap ) )
        # Print flowrules
        node = main.activeNodes[ 0 ]
        main.log.debug( main.CLIs[ node ].flows( jsonFormat=False ) )
        main.step( "Wait a minute then ping again" )
        # the wait is above
        PingResult = main.TRUE
        for i in range( 8, 18 ):
            ping = main.Mininet1.pingHost( src="h" + str( i ),
                                           target="h" + str( i + 10 ) )
            PingResult = PingResult and ping
            if ping == main.FALSE:
                main.log.warn( "Ping failed between h" + str( i ) +
                               " and h" + str( i + 10 ) )
            elif ping == main.TRUE:
                main.log.info( "Ping test passed!" )
                # Don't set PingResult or you'd override failures
        if PingResult == main.FALSE:
            main.log.error(
                "Intents have not been installed correctly, pings failed." )
            # TODO: pretty print
            main.log.warn( "ONOS1 intents: " )
            try:
                tmpIntents = onosCli.intents()
                main.log.warn( json.dumps( json.loads( tmpIntents ),
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )
            except ( ValueError, TypeError ):
                main.log.warn( repr( tmpIntents ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=PingResult,
            onpass="Intents have been installed correctly and pings work",
            onfail="Intents have not been installed correctly, pings failed." )

    def CASE5( self, main ):
        """
        Reading state of ONOS
        """
        import json
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        main.case( "Setting up and gathering data for current state" )
        # The general idea for this test case is to pull the state of
        # ( intents,flows, topology,... ) from each ONOS node
        # We can then compare them with each other and also with past states

        main.step( "Check that each switch has a master" )
        global mastershipState
        mastershipState = '[]'

        # Assert that each device has a master
        rolesNotNull = main.TRUE
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].rolesNotNull,
                             name="rolesNotNull-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            rolesNotNull = rolesNotNull and t.result
        utilities.assert_equals(
            expect=main.TRUE,
            actual=rolesNotNull,
            onpass="Each device has a master",
            onfail="Some devices don't have a master assigned" )

        main.step( "Get the Mastership of each switch from each controller" )
        ONOSMastership = []
        mastershipCheck = main.FALSE
        consistentMastership = True
        rolesResults = True
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].roles,
                             name="roles-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            ONOSMastership.append( t.result )

        for i in range( len( ONOSMastership ) ):
            node = str( main.activeNodes[ i ] + 1 )
            if not ONOSMastership[ i ] or "Error" in ONOSMastership[ i ]:
                main.log.error( "Error in getting ONOS" + node + " roles" )
                main.log.warn( "ONOS" + node + " mastership response: " +
                               repr( ONOSMastership[ i ] ) )
                rolesResults = False
        utilities.assert_equals(
            expect=True,
            actual=rolesResults,
            onpass="No error in reading roles output",
            onfail="Error in reading roles from ONOS" )

        main.step( "Check for consistency in roles from each controller" )
        if all( [ i == ONOSMastership[ 0 ] for i in ONOSMastership ] ):
            main.log.info(
                "Switch roles are consistent across all ONOS nodes" )
        else:
            consistentMastership = False
        utilities.assert_equals(
            expect=True,
            actual=consistentMastership,
            onpass="Switch roles are consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of switch roles" )

        if rolesResults and not consistentMastership:
            for i in range( len( main.activeNodes ) ):
                node = str( main.activeNodes[ i ] + 1 )
                try:
                    main.log.warn(
                        "ONOS" + node + " roles: ",
                        json.dumps(
                            json.loads( ONOSMastership[ i ] ),
                            sort_keys=True,
                            indent=4,
                            separators=( ',', ': ' ) ) )
                except ( ValueError, TypeError ):
                    main.log.warn( repr( ONOSMastership[ i ] ) )
        elif rolesResults and consistentMastership:
            mastershipCheck = main.TRUE
            mastershipState = ONOSMastership[ 0 ]

        main.step( "Get the intents from each controller" )
        global intentState
        intentState = []
        ONOSIntents = []
        intentCheck = main.FALSE
        consistentIntents = True
        intentsResults = True
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].intents,
                             name="intents-" + str( i ),
                             args=[],
                             kwargs={ 'jsonFormat': True } )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            ONOSIntents.append( t.result )

        for i in range( len( ONOSIntents ) ):
            node = str( main.activeNodes[ i ] + 1 )
            if not ONOSIntents[ i ] or "Error" in ONOSIntents[ i ]:
                main.log.error( "Error in getting ONOS" + node + " intents" )
                main.log.warn( "ONOS" + node + " intents response: " +
                               repr( ONOSIntents[ i ] ) )
                intentsResults = False
        utilities.assert_equals(
            expect=True,
            actual=intentsResults,
            onpass="No error in reading intents output",
            onfail="Error in reading intents from ONOS" )

        main.step( "Check for consistency in Intents from each controller" )
        if all( [ sorted( i ) == sorted( ONOSIntents[ 0 ] ) for i in ONOSIntents ] ):
            main.log.info( "Intents are consistent across all ONOS " +
                             "nodes" )
        else:
            consistentIntents = False
            main.log.error( "Intents not consistent" )
        utilities.assert_equals(
            expect=True,
            actual=consistentIntents,
            onpass="Intents are consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of intents" )

        if intentsResults:
            # Try to make it easy to figure out what is happening
            #
            # Intent      ONOS1      ONOS2    ...
            #  0x01     INSTALLED  INSTALLING
            #  ...        ...         ...
            #  ...        ...         ...
            title = "   Id"
            for n in main.activeNodes:
                title += " " * 10 + "ONOS" + str( n + 1 )
            main.log.warn( title )
            # get all intent keys in the cluster
            keys = []
            try:
                # Get the set of all intent keys
                for nodeStr in ONOSIntents:
                    node = json.loads( nodeStr )
                    for intent in node:
                        keys.append( intent.get( 'id' ) )
                keys = set( keys )
                # For each intent key, print the state on each node
                for key in keys:
                    row = "%-13s" % key
                    for nodeStr in ONOSIntents:
                        node = json.loads( nodeStr )
                        for intent in node:
                            if intent.get( 'id', "Error" ) == key:
                                row += "%-15s" % intent.get( 'state' )
                    main.log.warn( row )
                # End of intent state table
            except ValueError as e:
                main.log.exception( e )
                main.log.debug( "nodeStr was: " + repr( nodeStr ) )

        if intentsResults and not consistentIntents:
            # print the json objects
            n = str( main.activeNodes[ -1 ] + 1 )
            main.log.debug( "ONOS" + n + " intents: " )
            main.log.debug( json.dumps( json.loads( ONOSIntents[ -1 ] ),
                                        sort_keys=True,
                                        indent=4,
                                        separators=( ',', ': ' ) ) )
            for i in range( len( ONOSIntents ) ):
                node = str( main.activeNodes[ i ] + 1 )
                if ONOSIntents[ i ] != ONOSIntents[ -1 ]:
                    main.log.debug( "ONOS" + node + " intents: " )
                    main.log.debug( json.dumps( json.loads( ONOSIntents[ i ] ),
                                                sort_keys=True,
                                                indent=4,
                                                separators=( ',', ': ' ) ) )
                else:
                    main.log.debug( "ONOS" + node + " intents match ONOS" +
                                    n + " intents" )
        elif intentsResults and consistentIntents:
            intentCheck = main.TRUE
            intentState = ONOSIntents[ 0 ]

        main.step( "Get the flows from each controller" )
        global flowState
        flowState = []
        ONOSFlows = []
        ONOSFlowsJson = []
        flowCheck = main.FALSE
        consistentFlows = True
        flowsResults = True
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].flows,
                             name="flows-" + str( i ),
                             args=[],
                             kwargs={ 'jsonFormat': True } )
            threads.append( t )
            t.start()

        # NOTE: Flows command can take some time to run
        time.sleep( 30 )
        for t in threads:
            t.join()
            result = t.result
            ONOSFlows.append( result )

        for i in range( len( ONOSFlows ) ):
            num = str( main.activeNodes[ i ] + 1 )
            if not ONOSFlows[ i ] or "Error" in ONOSFlows[ i ]:
                main.log.error( "Error in getting ONOS" + num + " flows" )
                main.log.warn( "ONOS" + num + " flows response: " +
                               repr( ONOSFlows[ i ] ) )
                flowsResults = False
                ONOSFlowsJson.append( None )
            else:
                try:
                    ONOSFlowsJson.append( json.loads( ONOSFlows[ i ] ) )
                except ( ValueError, TypeError ):
                    # FIXME: change this to log.error?
                    main.log.exception( "Error in parsing ONOS" + num +
                                        " response as json." )
                    main.log.error( repr( ONOSFlows[ i ] ) )
                    ONOSFlowsJson.append( None )
                    flowsResults = False
        utilities.assert_equals(
            expect=True,
            actual=flowsResults,
            onpass="No error in reading flows output",
            onfail="Error in reading flows from ONOS" )

        main.step( "Check for consistency in Flows from each controller" )
        tmp = [ len( i ) == len( ONOSFlowsJson[ 0 ] ) for i in ONOSFlowsJson ]
        if all( tmp ):
            main.log.info( "Flow count is consistent across all ONOS nodes" )
        else:
            consistentFlows = False
        utilities.assert_equals(
            expect=True,
            actual=consistentFlows,
            onpass="The flow count is consistent across all ONOS nodes",
            onfail="ONOS nodes have different flow counts" )

        if flowsResults and not consistentFlows:
            for i in range( len( ONOSFlows ) ):
                node = str( main.activeNodes[ i ] + 1 )
                try:
                    main.log.warn(
                        "ONOS" + node + " flows: " +
                        json.dumps( json.loads( ONOSFlows[ i ] ), sort_keys=True,
                                    indent=4, separators=( ',', ': ' ) ) )
                except ( ValueError, TypeError ):
                    main.log.warn( "ONOS" + node + " flows: " +
                                   repr( ONOSFlows[ i ] ) )
        elif flowsResults and consistentFlows:
            flowCheck = main.TRUE
            flowState = ONOSFlows[ 0 ]

        main.step( "Get the OF Table entries" )
        global flows
        flows = []
        for i in range( 1, 29 ):
            flows.append( main.Mininet1.getFlowTable( "s" + str( i ), version="1.3", debug=False ) )
        if flowCheck == main.FALSE:
            for table in flows:
                main.log.warn( table )
        # TODO: Compare switch flow tables with ONOS flow tables

        main.step( "Start continuous pings" )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source1' ],
            target=main.params[ 'PING' ][ 'target1' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source2' ],
            target=main.params[ 'PING' ][ 'target2' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source3' ],
            target=main.params[ 'PING' ][ 'target3' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source4' ],
            target=main.params[ 'PING' ][ 'target4' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source5' ],
            target=main.params[ 'PING' ][ 'target5' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source6' ],
            target=main.params[ 'PING' ][ 'target6' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source7' ],
            target=main.params[ 'PING' ][ 'target7' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source8' ],
            target=main.params[ 'PING' ][ 'target8' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source9' ],
            target=main.params[ 'PING' ][ 'target9' ],
            pingTime=500 )
        main.Mininet2.pingLong(
            src=main.params[ 'PING' ][ 'source10' ],
            target=main.params[ 'PING' ][ 'target10' ],
            pingTime=500 )

        main.step( "Collecting topology information from ONOS" )
        devices = []
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].devices,
                             name="devices-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            devices.append( t.result )
        hosts = []
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].hosts,
                             name="hosts-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            try:
                hosts.append( json.loads( t.result ) )
            except ( ValueError, TypeError ):
                # FIXME: better handling of this, print which node
                #        Maybe use thread name?
                main.log.exception( "Error parsing json output of hosts" )
                main.log.warn( repr( t.result ) )
                hosts.append( None )

        ports = []
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].ports,
                             name="ports-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            ports.append( t.result )
        links = []
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].links,
                             name="links-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            links.append( t.result )
        clusters = []
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].clusters,
                             name="clusters-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            clusters.append( t.result )
        # Compare json objects for hosts and dataplane clusters

        # hosts
        main.step( "Host view is consistent across ONOS nodes" )
        consistentHostsResult = main.TRUE
        for controller in range( len( hosts ) ):
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if hosts[ controller ] and "Error" not in hosts[ controller ]:
                if hosts[ controller ] == hosts[ 0 ]:
                    continue
                else:  # hosts not consistent
                    main.log.error( "hosts from ONOS" +
                                     controllerStr +
                                     " is inconsistent with ONOS1" )
                    main.log.warn( repr( hosts[ controller ] ) )
                    consistentHostsResult = main.FALSE

            else:
                main.log.error( "Error in getting ONOS hosts from ONOS" +
                                 controllerStr )
                consistentHostsResult = main.FALSE
                main.log.warn( "ONOS" + controllerStr +
                               " hosts response: " +
                               repr( hosts[ controller ] ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=consistentHostsResult,
            onpass="Hosts view is consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of hosts" )

        main.step( "Each host has an IP address" )
        ipResult = main.TRUE
        for controller in range( 0, len( hosts ) ):
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if hosts[ controller ]:
                for host in hosts[ controller ]:
                    if not host.get( 'ipAddresses', [] ):
                        main.log.error( "Error with host ips on controller" +
                                        controllerStr + ": " + str( host ) )
                        ipResult = main.FALSE
        utilities.assert_equals(
            expect=main.TRUE,
            actual=ipResult,
            onpass="The ips of the hosts aren't empty",
            onfail="The ip of at least one host is missing" )

        # Strongly connected clusters of devices
        main.step( "Cluster view is consistent across ONOS nodes" )
        consistentClustersResult = main.TRUE
        for controller in range( len( clusters ) ):
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if "Error" not in clusters[ controller ]:
                if clusters[ controller ] == clusters[ 0 ]:
                    continue
                else:  # clusters not consistent
                    main.log.error( "clusters from ONOS" + controllerStr +
                                     " is inconsistent with ONOS1" )
                    consistentClustersResult = main.FALSE

            else:
                main.log.error( "Error in getting dataplane clusters " +
                                 "from ONOS" + controllerStr )
                consistentClustersResult = main.FALSE
                main.log.warn( "ONOS" + controllerStr +
                               " clusters response: " +
                               repr( clusters[ controller ] ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=consistentClustersResult,
            onpass="Clusters view is consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of clusters" )
        if not consistentClustersResult:
            main.log.debug( clusters )

        # there should always only be one cluster
        main.step( "Cluster view correct across ONOS nodes" )
        try:
            numClusters = len( json.loads( clusters[ 0 ] ) )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing clusters[0]: " +
                                repr( clusters[ 0 ] ) )
            numClusters = "ERROR"
        clusterResults = main.FALSE
        if numClusters == 1:
            clusterResults = main.TRUE
        utilities.assert_equals(
            expect=1,
            actual=numClusters,
            onpass="ONOS shows 1 SCC",
            onfail="ONOS shows " + str( numClusters ) + " SCCs" )

        main.step( "Comparing ONOS topology to MN" )
        devicesResults = main.TRUE
        linksResults = main.TRUE
        hostsResults = main.TRUE
        mnSwitches = main.Mininet1.getSwitches()
        mnLinks = main.Mininet1.getLinks()
        mnHosts = main.Mininet1.getHosts()
        for controller in main.activeNodes:
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if devices[ controller ] and ports[ controller ] and\
                    "Error" not in devices[ controller ] and\
                    "Error" not in ports[ controller ]:
                currentDevicesResult = main.Mininet1.compareSwitches(
                        mnSwitches,
                        json.loads( devices[ controller ] ),
                        json.loads( ports[ controller ] ) )
            else:
                currentDevicesResult = main.FALSE
            utilities.assert_equals( expect=main.TRUE,
                                     actual=currentDevicesResult,
                                     onpass="ONOS" + controllerStr +
                                     " Switches view is correct",
                                     onfail="ONOS" + controllerStr +
                                     " Switches view is incorrect" )
            if links[ controller ] and "Error" not in links[ controller ]:
                currentLinksResult = main.Mininet1.compareLinks(
                        mnSwitches, mnLinks,
                        json.loads( links[ controller ] ) )
            else:
                currentLinksResult = main.FALSE
            utilities.assert_equals( expect=main.TRUE,
                                     actual=currentLinksResult,
                                     onpass="ONOS" + controllerStr +
                                     " links view is correct",
                                     onfail="ONOS" + controllerStr +
                                     " links view is incorrect" )

            if hosts[ controller ] and "Error" not in hosts[ controller ]:
                currentHostsResult = main.Mininet1.compareHosts(
                        mnHosts,
                        hosts[ controller ] )
            else:
                currentHostsResult = main.FALSE
            utilities.assert_equals( expect=main.TRUE,
                                     actual=currentHostsResult,
                                     onpass="ONOS" + controllerStr +
                                     " hosts exist in Mininet",
                                     onfail="ONOS" + controllerStr +
                                     " hosts don't match Mininet" )

            devicesResults = devicesResults and currentDevicesResult
            linksResults = linksResults and currentLinksResult
            hostsResults = hostsResults and currentHostsResult

        main.step( "Device information is correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=devicesResults,
            onpass="Device information is correct",
            onfail="Device information is incorrect" )

        main.step( "Links are correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=linksResults,
            onpass="Link are correct",
            onfail="Links are incorrect" )

        main.step( "Hosts are correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=hostsResults,
            onpass="Hosts are correct",
            onfail="Hosts are incorrect" )

    def CASE61( self, main ):
        """
        The Failure case.
        """
        import math
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        main.case( "Partition ONOS nodes into two distinct partitions" )

        main.step( "Checking ONOS Logs for errors" )
        for node in main.nodes:
            main.log.debug( "Checking logs for errors on " + node.name + ":" )
            main.log.warn( main.ONOSbench.checkLogs( node.ip_address ) )

        main.log.debug( main.CLIs[ 0 ].roles( jsonFormat=False ) )

        n = len( main.nodes )  # Number of nodes
        p = ( ( n + 1 ) / 2 ) + 1  # Number of partitions
        main.partition = [ 0 ]  # ONOS node to partition, listed by index in main.nodes
        if n > 3:
            main.partition.append( p - 1 )
            # NOTE: This only works for cluster sizes of 3,5, or 7.

        main.step( "Partitioning ONOS nodes" )
        nodeList = [ str( i + 1 ) for i in main.partition ]
        main.log.info( "Nodes to be partitioned: " + str( nodeList ) )
        partitionResults = main.TRUE
        for i in range( 0, n ):
            this = main.nodes[ i ]
            if i not in main.partition:
                for j in main.partition:
                    foe = main.nodes[ j ]
                    main.log.warn( "Setting IP Tables rule from {} to {}. ".format( this.ip_address, foe.ip_address ) )
                    #CMD HERE
                    cmdStr = "sudo iptables -A {} -d {} -s {} -j DROP".format( "INPUT", this.ip_address, foe.ip_address )
                    this.handle.sendline( cmdStr )
                    this.handle.expect( "\$" )
                    main.log.debug( this.handle.before )
            else:
                for j in range( 0, n ):
                    if j not in main.partition:
                        foe = main.nodes[ j ]
                        main.log.warn( "Setting IP Tables rule from {} to {}. ".format( this.ip_address, foe.ip_address ) )
                        #CMD HERE
                        cmdStr = "sudo iptables -A {} -d {} -s {} -j DROP".format( "INPUT", this.ip_address, foe.ip_address )
                        this.handle.sendline( cmdStr )
                        this.handle.expect( "\$" )
                        main.log.debug( this.handle.before )
                main.activeNodes.remove( i )
        # NOTE: When dynamic clustering is finished, we need to start checking
        #       main.partion nodes still work when partitioned
        utilities.assert_equals( expect=main.TRUE, actual=partitionResults,
                                 onpass="Firewall rules set successfully",
                                 onfail="Error setting firewall rules" )

        main.step( "Sleeping 60 seconds" )
        time.sleep( 60 )

    def CASE62( self, main ):
        """
        Healing Partition
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        assert main.partition, "main.partition not defined"
        main.case( "Healing Partition" )

        main.step( "Deleteing firewall rules" )
        healResults = main.TRUE
        for node in main.nodes:
            cmdStr = "sudo iptables -F"
            node.handle.sendline( cmdStr )
            node.handle.expect( "\$" )
            main.log.debug( node.handle.before )
        utilities.assert_equals( expect=main.TRUE, actual=healResults,
                                 onpass="Firewall rules removed",
                                 onfail="Error removing firewall rules" )

        for node in main.partition:
            main.activeNodes.append( node )
        main.activeNodes.sort()
        try:
            assert list( set( main.activeNodes ) ) == main.activeNodes,\
                   "List of active nodes has duplicates, this likely indicates something was run out of order"
        except AssertionError:
            main.log.exception( "" )
            main.cleanup()
            main.exit()

        main.step( "Checking ONOS nodes" )
        nodeResults = utilities.retry( main.HA.nodesCheck,
                                       False,
                                       args=[ main.activeNodes ],
                                       sleep=15,
                                       attempts=5 )

        utilities.assert_equals( expect=True, actual=nodeResults,
                                 onpass="Nodes check successful",
                                 onfail="Nodes check NOT successful" )

        if not nodeResults:
            for i in main.activeNodes:
                cli = main.CLIs[ i ]
                main.log.debug( "{} components not ACTIVE: \n{}".format(
                    cli.name,
                    cli.sendline( "scr:list | grep -v ACTIVE" ) ) )
            main.log.error( "Failed to start ONOS, stopping test" )
            main.cleanup()
            main.exit()

    def CASE7( self, main ):
        """
        Check state after ONOS failure
        """
        import json
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        try:
            main.partition
        except AttributeError:
            main.partition = []

        main.case( "Running ONOS Constant State Tests" )

        main.step( "Check that each switch has a master" )
        # Assert that each device has a master
        rolesNotNull = main.TRUE
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].rolesNotNull,
                             name="rolesNotNull-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            rolesNotNull = rolesNotNull and t.result
        utilities.assert_equals(
            expect=main.TRUE,
            actual=rolesNotNull,
            onpass="Each device has a master",
            onfail="Some devices don't have a master assigned" )

        main.step( "Read device roles from ONOS" )
        ONOSMastership = []
        mastershipCheck = main.FALSE
        consistentMastership = True
        rolesResults = True
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].roles,
                             name="roles-" + str( i ),
                             args=[] )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            ONOSMastership.append( t.result )

        for i in range( len( ONOSMastership ) ):
            node = str( main.activeNodes[ i ] + 1 )
            if not ONOSMastership[ i ] or "Error" in ONOSMastership[ i ]:
                main.log.error( "Error in getting ONOS" + node + " roles" )
                main.log.warn( "ONOS" + node + " mastership response: " +
                               repr( ONOSMastership[ i ] ) )
                rolesResults = False
        utilities.assert_equals(
            expect=True,
            actual=rolesResults,
            onpass="No error in reading roles output",
            onfail="Error in reading roles from ONOS" )

        main.step( "Check for consistency in roles from each controller" )
        if all( [ i == ONOSMastership[ 0 ] for i in ONOSMastership ] ):
            main.log.info(
                "Switch roles are consistent across all ONOS nodes" )
        else:
            consistentMastership = False
        utilities.assert_equals(
            expect=True,
            actual=consistentMastership,
            onpass="Switch roles are consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of switch roles" )

        if rolesResults and not consistentMastership:
            for i in range( len( ONOSMastership ) ):
                node = str( main.activeNodes[ i ] + 1 )
                main.log.warn( "ONOS" + node + " roles: ",
                               json.dumps( json.loads( ONOSMastership[ i ] ),
                                           sort_keys=True,
                                           indent=4,
                                           separators=( ',', ': ' ) ) )

        # NOTE: we expect mastership to change on controller failure

        main.step( "Get the intents and compare across all nodes" )
        ONOSIntents = []
        intentCheck = main.FALSE
        consistentIntents = True
        intentsResults = True
        threads = []
        for i in main.activeNodes:
            t = main.Thread( target=main.CLIs[ i ].intents,
                             name="intents-" + str( i ),
                             args=[],
                             kwargs={ 'jsonFormat': True } )
            threads.append( t )
            t.start()

        for t in threads:
            t.join()
            ONOSIntents.append( t.result )

        for i in range( len( ONOSIntents ) ):
            node = str( main.activeNodes[ i ] + 1 )
            if not ONOSIntents[ i ] or "Error" in ONOSIntents[ i ]:
                main.log.error( "Error in getting ONOS" + node + " intents" )
                main.log.warn( "ONOS" + node + " intents response: " +
                               repr( ONOSIntents[ i ] ) )
                intentsResults = False
        utilities.assert_equals(
            expect=True,
            actual=intentsResults,
            onpass="No error in reading intents output",
            onfail="Error in reading intents from ONOS" )

        main.step( "Check for consistency in Intents from each controller" )
        if all( [ sorted( i ) == sorted( ONOSIntents[ 0 ] ) for i in ONOSIntents ] ):
            main.log.info( "Intents are consistent across all ONOS " +
                             "nodes" )
        else:
            consistentIntents = False

        # Try to make it easy to figure out what is happening
        #
        # Intent      ONOS1      ONOS2    ...
        #  0x01     INSTALLED  INSTALLING
        #  ...        ...         ...
        #  ...        ...         ...
        title = "   ID"
        for n in main.activeNodes:
            title += " " * 10 + "ONOS" + str( n + 1 )
        main.log.warn( title )
        # get all intent keys in the cluster
        keys = []
        for nodeStr in ONOSIntents:
            node = json.loads( nodeStr )
            for intent in node:
                keys.append( intent.get( 'id' ) )
        keys = set( keys )
        for key in keys:
            row = "%-13s" % key
            for nodeStr in ONOSIntents:
                node = json.loads( nodeStr )
                for intent in node:
                    if intent.get( 'id' ) == key:
                        row += "%-15s" % intent.get( 'state' )
            main.log.warn( row )
        # End table view

        utilities.assert_equals(
            expect=True,
            actual=consistentIntents,
            onpass="Intents are consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of intents" )
        intentStates = []
        for node in ONOSIntents:  # Iter through ONOS nodes
            nodeStates = []
            # Iter through intents of a node
            try:
                for intent in json.loads( node ):
                    nodeStates.append( intent[ 'state' ] )
            except ( ValueError, TypeError ):
                main.log.exception( "Error in parsing intents" )
                main.log.error( repr( node ) )
            intentStates.append( nodeStates )
            out = [ ( i, nodeStates.count( i ) ) for i in set( nodeStates ) ]
            main.log.info( dict( out ) )

        if intentsResults and not consistentIntents:
            for i in range( len( main.activeNodes ) ):
                node = str( main.activeNodes[ i ] + 1 )
                main.log.warn( "ONOS" + node + " intents: " )
                main.log.warn( json.dumps(
                    json.loads( ONOSIntents[ i ] ),
                    sort_keys=True,
                    indent=4,
                    separators=( ',', ': ' ) ) )
        elif intentsResults and consistentIntents:
            intentCheck = main.TRUE

        # NOTE: Store has no durability, so intents are lost across system
        #       restarts
        main.step( "Compare current intents with intents before the failure" )
        # NOTE: this requires case 5 to pass for intentState to be set.
        #      maybe we should stop the test if that fails?
        sameIntents = main.FALSE
        try:
            intentState
        except NameError:
            main.log.warn( "No previous intent state was saved" )
        else:
            if intentState and intentState == ONOSIntents[ 0 ]:
                sameIntents = main.TRUE
                main.log.info( "Intents are consistent with before failure" )
            # TODO: possibly the states have changed? we may need to figure out
            #       what the acceptable states are
            elif len( intentState ) == len( ONOSIntents[ 0 ] ):
                sameIntents = main.TRUE
                try:
                    before = json.loads( intentState )
                    after = json.loads( ONOSIntents[ 0 ] )
                    for intent in before:
                        if intent not in after:
                            sameIntents = main.FALSE
                            main.log.debug( "Intent is not currently in ONOS " +
                                            "(at least in the same form):" )
                            main.log.debug( json.dumps( intent ) )
                except ( ValueError, TypeError ):
                    main.log.exception( "Exception printing intents" )
                    main.log.debug( repr( ONOSIntents[ 0 ] ) )
                    main.log.debug( repr( intentState ) )
            if sameIntents == main.FALSE:
                try:
                    main.log.debug( "ONOS intents before: " )
                    main.log.debug( json.dumps( json.loads( intentState ),
                                                sort_keys=True, indent=4,
                                                separators=( ',', ': ' ) ) )
                    main.log.debug( "Current ONOS intents: " )
                    main.log.debug( json.dumps( json.loads( ONOSIntents[ 0 ] ),
                                                sort_keys=True, indent=4,
                                                separators=( ',', ': ' ) ) )
                except ( ValueError, TypeError ):
                    main.log.exception( "Exception printing intents" )
                    main.log.debug( repr( ONOSIntents[ 0 ] ) )
                    main.log.debug( repr( intentState ) )
            utilities.assert_equals(
                expect=main.TRUE,
                actual=sameIntents,
                onpass="Intents are consistent with before failure",
                onfail="The Intents changed during failure" )
        intentCheck = intentCheck and sameIntents

        main.step( "Get the OF Table entries and compare to before " +
                   "component failure" )
        FlowTables = main.TRUE
        for i in range( 28 ):
            main.log.info( "Checking flow table on s" + str( i + 1 ) )
            tmpFlows = main.Mininet1.getFlowTable( "s" + str( i + 1 ), version="1.3", debug=False )
            curSwitch = main.Mininet1.flowTableComp( flows[ i ], tmpFlows )
            FlowTables = FlowTables and curSwitch
            if curSwitch == main.FALSE:
                main.log.warn( "Differences in flow table for switch: s{}".format( i + 1 ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=FlowTables,
            onpass="No changes were found in the flow tables",
            onfail="Changes were found in the flow tables" )

        main.Mininet2.pingLongKill()
        """
        main.step( "Check the continuous pings to ensure that no packets " +
                   "were dropped during component failure" )
        main.Mininet2.pingKill( main.params[ 'TESTONUSER' ],
                                main.params[ 'TESTONIP' ] )
        LossInPings = main.FALSE
        # NOTE: checkForLoss returns main.FALSE with 0% packet loss
        for i in range( 8, 18 ):
            main.log.info(
                "Checking for a loss in pings along flow from s" +
                str( i ) )
            LossInPings = main.Mininet2.checkForLoss(
                "/tmp/ping.h" +
                str( i ) ) or LossInPings
        if LossInPings == main.TRUE:
            main.log.info( "Loss in ping detected" )
        elif LossInPings == main.ERROR:
            main.log.info( "There are multiple mininet process running" )
        elif LossInPings == main.FALSE:
            main.log.info( "No Loss in the pings" )
            main.log.info( "No loss of dataplane connectivity" )
        utilities.assert_equals(
            expect=main.FALSE,
            actual=LossInPings,
            onpass="No Loss of connectivity",
            onfail="Loss of dataplane connectivity detected" )
        """
        main.step( "Leadership Election is still functional" )
        # Test of LeadershipElection
        leaderList = []

        partitioned = []
        for i in main.partition:
            partitioned.append( main.nodes[ i ].ip_address )
        leaderResult = main.TRUE

        for i in main.activeNodes:
            cli = main.CLIs[ i ]
            leaderN = cli.electionTestLeader()
            leaderList.append( leaderN )
            if leaderN == main.FALSE:
                # error in response
                main.log.error( "Something is wrong with " +
                                 "electionTestLeader function, check the" +
                                 " error logs" )
                leaderResult = main.FALSE
            elif leaderN is None:
                main.log.error( cli.name +
                                 " shows no leader for the election-app was" +
                                 " elected after the old one died" )
                leaderResult = main.FALSE
            elif leaderN in partitioned:
                main.log.error( cli.name + " shows " + str( leaderN ) +
                                 " as leader for the election-app, but it " +
                                 "was partitioned" )
                leaderResult = main.FALSE
        if len( set( leaderList ) ) != 1:
            leaderResult = main.FALSE
            main.log.error(
                "Inconsistent view of leader for the election test app" )
            # TODO: print the list
        utilities.assert_equals(
            expect=main.TRUE,
            actual=leaderResult,
            onpass="Leadership election passed",
            onfail="Something went wrong with Leadership election" )

    def CASE8( self, main ):
        """
        Compare topo
        """
        import json
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        main.case( "Compare ONOS Topology view to Mininet topology" )
        main.caseExplanation = "Compare topology objects between Mininet" +\
                                " and ONOS"
        topoResult = main.FALSE
        topoFailMsg = "ONOS topology don't match Mininet"
        elapsed = 0
        count = 0
        main.step( "Comparing ONOS topology to MN topology" )
        startTime = time.time()
        # Give time for Gossip to work
        while topoResult == main.FALSE and ( elapsed < 60 or count < 3 ):
            devicesResults = main.TRUE
            linksResults = main.TRUE
            hostsResults = main.TRUE
            hostAttachmentResults = True
            count += 1
            cliStart = time.time()
            devices = []
            threads = []
            for i in main.activeNodes:
                t = main.Thread( target=utilities.retry,
                                 name="devices-" + str( i ),
                                 args=[ main.CLIs[ i ].devices, [ None ] ],
                                 kwargs={ 'sleep': 5, 'attempts': 5,
                                           'randomTime': True } )
                threads.append( t )
                t.start()

            for t in threads:
                t.join()
                devices.append( t.result )
            hosts = []
            ipResult = main.TRUE
            threads = []
            for i in main.activeNodes:
                t = main.Thread( target=utilities.retry,
                                 name="hosts-" + str( i ),
                                 args=[ main.CLIs[ i ].hosts, [ None ] ],
                                 kwargs={ 'sleep': 5, 'attempts': 5,
                                           'randomTime': True } )
                threads.append( t )
                t.start()

            for t in threads:
                t.join()
                try:
                    hosts.append( json.loads( t.result ) )
                except ( ValueError, TypeError ):
                    main.log.exception( "Error parsing hosts results" )
                    main.log.error( repr( t.result ) )
                    hosts.append( None )
            for controller in range( 0, len( hosts ) ):
                controllerStr = str( main.activeNodes[ controller ] + 1 )
                if hosts[ controller ]:
                    for host in hosts[ controller ]:
                        if host is None or host.get( 'ipAddresses', [] ) == []:
                            main.log.error(
                                "Error with host ipAddresses on controller" +
                                controllerStr + ": " + str( host ) )
                            ipResult = main.FALSE
            ports = []
            threads = []
            for i in main.activeNodes:
                t = main.Thread( target=utilities.retry,
                                 name="ports-" + str( i ),
                                 args=[ main.CLIs[ i ].ports, [ None ] ],
                                 kwargs={ 'sleep': 5, 'attempts': 5,
                                           'randomTime': True } )
                threads.append( t )
                t.start()

            for t in threads:
                t.join()
                ports.append( t.result )
            links = []
            threads = []
            for i in main.activeNodes:
                t = main.Thread( target=utilities.retry,
                                 name="links-" + str( i ),
                                 args=[ main.CLIs[ i ].links, [ None ] ],
                                 kwargs={ 'sleep': 5, 'attempts': 5,
                                           'randomTime': True } )
                threads.append( t )
                t.start()

            for t in threads:
                t.join()
                links.append( t.result )
            clusters = []
            threads = []
            for i in main.activeNodes:
                t = main.Thread( target=utilities.retry,
                                 name="clusters-" + str( i ),
                                 args=[ main.CLIs[ i ].clusters, [ None ] ],
                                 kwargs={ 'sleep': 5, 'attempts': 5,
                                           'randomTime': True } )
                threads.append( t )
                t.start()

            for t in threads:
                t.join()
                clusters.append( t.result )

            elapsed = time.time() - startTime
            cliTime = time.time() - cliStart
            print "Elapsed time: " + str( elapsed )
            print "CLI time: " + str( cliTime )

            if all( e is None for e in devices ) and\
               all( e is None for e in hosts ) and\
               all( e is None for e in ports ) and\
               all( e is None for e in links ) and\
               all( e is None for e in clusters ):
                topoFailMsg = "Could not get topology from ONOS"
                main.log.error( topoFailMsg )
                continue  # Try again, No use trying to compare

            mnSwitches = main.Mininet1.getSwitches()
            mnLinks = main.Mininet1.getLinks()
            mnHosts = main.Mininet1.getHosts()
            for controller in range( len( main.activeNodes ) ):
                controllerStr = str( main.activeNodes[ controller ] + 1 )
                if devices[ controller ] and ports[ controller ] and\
                        "Error" not in devices[ controller ] and\
                        "Error" not in ports[ controller ]:

                    try:
                        currentDevicesResult = main.Mininet1.compareSwitches(
                                mnSwitches,
                                json.loads( devices[ controller ] ),
                                json.loads( ports[ controller ] ) )
                    except ( TypeError, ValueError ) as e:
                        main.log.exception( "Object not as expected; devices={!r}\nports={!r}".format(
                            devices[ controller ], ports[ controller ] ) )
                else:
                    currentDevicesResult = main.FALSE
                utilities.assert_equals( expect=main.TRUE,
                                         actual=currentDevicesResult,
                                         onpass="ONOS" + controllerStr +
                                         " Switches view is correct",
                                         onfail="ONOS" + controllerStr +
                                         " Switches view is incorrect" )

                if links[ controller ] and "Error" not in links[ controller ]:
                    currentLinksResult = main.Mininet1.compareLinks(
                            mnSwitches, mnLinks,
                            json.loads( links[ controller ] ) )
                else:
                    currentLinksResult = main.FALSE
                utilities.assert_equals( expect=main.TRUE,
                                         actual=currentLinksResult,
                                         onpass="ONOS" + controllerStr +
                                         " links view is correct",
                                         onfail="ONOS" + controllerStr +
                                         " links view is incorrect" )
                if hosts[ controller ] and "Error" not in hosts[ controller ]:
                    currentHostsResult = main.Mininet1.compareHosts(
                            mnHosts,
                            hosts[ controller ] )
                elif hosts[ controller ] == []:
                    currentHostsResult = main.TRUE
                else:
                    currentHostsResult = main.FALSE
                utilities.assert_equals( expect=main.TRUE,
                                         actual=currentHostsResult,
                                         onpass="ONOS" + controllerStr +
                                         " hosts exist in Mininet",
                                         onfail="ONOS" + controllerStr +
                                         " hosts don't match Mininet" )
                # CHECKING HOST ATTACHMENT POINTS
                hostAttachment = True
                zeroHosts = False
                # FIXME: topo-HA/obelisk specific mappings:
                # key is mac and value is dpid
                mappings = {}
                for i in range( 1, 29 ):  # hosts 1 through 28
                    # set up correct variables:
                    macId = "00:" * 5 + hex( i ).split( "0x" )[ 1 ].upper().zfill( 2 )
                    if i == 1:
                        deviceId = "1000".zfill( 16 )
                    elif i == 2:
                        deviceId = "2000".zfill( 16 )
                    elif i == 3:
                        deviceId = "3000".zfill( 16 )
                    elif i == 4:
                        deviceId = "3004".zfill( 16 )
                    elif i == 5:
                        deviceId = "5000".zfill( 16 )
                    elif i == 6:
                        deviceId = "6000".zfill( 16 )
                    elif i == 7:
                        deviceId = "6007".zfill( 16 )
                    elif i >= 8 and i <= 17:
                        dpid = '3' + str( i ).zfill( 3 )
                        deviceId = dpid.zfill( 16 )
                    elif i >= 18 and i <= 27:
                        dpid = '6' + str( i ).zfill( 3 )
                        deviceId = dpid.zfill( 16 )
                    elif i == 28:
                        deviceId = "2800".zfill( 16 )
                    mappings[ macId ] = deviceId
                if hosts[ controller ] is not None and "Error" not in hosts[ controller ]:
                    if hosts[ controller ] == []:
                        main.log.warn( "There are no hosts discovered" )
                        zeroHosts = True
                    else:
                        for host in hosts[ controller ]:
                            mac = None
                            location = None
                            device = None
                            port = None
                            try:
                                mac = host.get( 'mac' )
                                assert mac, "mac field could not be found for this host object"

                                location = host.get( 'location' )
                                assert location, "location field could not be found for this host object"

                                # Trim the protocol identifier off deviceId
                                device = str( location.get( 'elementId' ) ).split( ':' )[ 1 ]
                                assert device, "elementId field could not be found for this host location object"

                                port = location.get( 'port' )
                                assert port, "port field could not be found for this host location object"

                                # Now check if this matches where they should be
                                if mac and device and port:
                                    if str( port ) != "1":
                                        main.log.error( "The attachment port is incorrect for " +
                                                        "host " + str( mac ) +
                                                        ". Expected: 1 Actual: " + str( port ) )
                                        hostAttachment = False
                                    if device != mappings[ str( mac ) ]:
                                        main.log.error( "The attachment device is incorrect for " +
                                                        "host " + str( mac ) +
                                                        ". Expected: " + mappings[ str( mac ) ] +
                                                        " Actual: " + device )
                                        hostAttachment = False
                                else:
                                    hostAttachment = False
                            except AssertionError:
                                main.log.exception( "Json object not as expected" )
                                main.log.error( repr( host ) )
                                hostAttachment = False
                else:
                    main.log.error( "No hosts json output or \"Error\"" +
                                    " in output. hosts = " +
                                    repr( hosts[ controller ] ) )
                if zeroHosts is False:
                    hostAttachment = True

                # END CHECKING HOST ATTACHMENT POINTS
                devicesResults = devicesResults and currentDevicesResult
                linksResults = linksResults and currentLinksResult
                hostsResults = hostsResults and currentHostsResult
                hostAttachmentResults = hostAttachmentResults and\
                                        hostAttachment
                topoResult = ( devicesResults and linksResults
                               and hostsResults and ipResult and
                               hostAttachmentResults )
        utilities.assert_equals( expect=True,
                                 actual=topoResult,
                                 onpass="ONOS topology matches Mininet",
                                 onfail=topoFailMsg )
        # End of While loop to pull ONOS state

        # Compare json objects for hosts and dataplane clusters

        # hosts
        main.step( "Hosts view is consistent across all ONOS nodes" )
        consistentHostsResult = main.TRUE
        for controller in range( len( hosts ) ):
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if hosts[ controller ] is not None and "Error" not in hosts[ controller ]:
                if hosts[ controller ] == hosts[ 0 ]:
                    continue
                else:  # hosts not consistent
                    main.log.error( "hosts from ONOS" + controllerStr +
                                     " is inconsistent with ONOS1" )
                    main.log.warn( repr( hosts[ controller ] ) )
                    consistentHostsResult = main.FALSE

            else:
                main.log.error( "Error in getting ONOS hosts from ONOS" +
                                 controllerStr )
                consistentHostsResult = main.FALSE
                main.log.warn( "ONOS" + controllerStr +
                               " hosts response: " +
                               repr( hosts[ controller ] ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=consistentHostsResult,
            onpass="Hosts view is consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of hosts" )

        main.step( "Hosts information is correct" )
        hostsResults = hostsResults and ipResult
        utilities.assert_equals(
            expect=main.TRUE,
            actual=hostsResults,
            onpass="Host information is correct",
            onfail="Host information is incorrect" )

        main.step( "Host attachment points to the network" )
        utilities.assert_equals(
            expect=True,
            actual=hostAttachmentResults,
            onpass="Hosts are correctly attached to the network",
            onfail="ONOS did not correctly attach hosts to the network" )

        # Strongly connected clusters of devices
        main.step( "Clusters view is consistent across all ONOS nodes" )
        consistentClustersResult = main.TRUE
        for controller in range( len( clusters ) ):
            controllerStr = str( main.activeNodes[ controller ] + 1 )
            if "Error" not in clusters[ controller ]:
                if clusters[ controller ] == clusters[ 0 ]:
                    continue
                else:  # clusters not consistent
                    main.log.error( "clusters from ONOS" +
                                     controllerStr +
                                     " is inconsistent with ONOS1" )
                    consistentClustersResult = main.FALSE
            else:
                main.log.error( "Error in getting dataplane clusters " +
                                 "from ONOS" + controllerStr )
                consistentClustersResult = main.FALSE
                main.log.warn( "ONOS" + controllerStr +
                               " clusters response: " +
                               repr( clusters[ controller ] ) )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=consistentClustersResult,
            onpass="Clusters view is consistent across all ONOS nodes",
            onfail="ONOS nodes have different views of clusters" )
        if not consistentClustersResult:
            main.log.debug( clusters )

        main.step( "There is only one SCC" )
        # there should always only be one cluster
        try:
            numClusters = len( json.loads( clusters[ 0 ] ) )
        except ( ValueError, TypeError ):
            main.log.exception( "Error parsing clusters[0]: " +
                                repr( clusters[ 0 ] ) )
            numClusters = "ERROR"
        clusterResults = main.FALSE
        if numClusters == 1:
            clusterResults = main.TRUE
        utilities.assert_equals(
            expect=1,
            actual=numClusters,
            onpass="ONOS shows 1 SCC",
            onfail="ONOS shows " + str( numClusters ) + " SCCs" )

        topoResult = ( devicesResults and linksResults
                       and hostsResults and consistentHostsResult
                       and consistentClustersResult and clusterResults
                       and ipResult and hostAttachmentResults )

        topoResult = topoResult and int( count <= 2 )
        note = "note it takes about " + str( int( cliTime ) ) + \
            " seconds for the test to make all the cli calls to fetch " +\
            "the topology from each ONOS instance"
        main.log.info(
            "Very crass estimate for topology discovery/convergence( " +
            str( note ) + " ): " + str( elapsed ) + " seconds, " +
            str( count ) + " tries" )

        main.step( "Device information is correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=devicesResults,
            onpass="Device information is correct",
            onfail="Device information is incorrect" )

        main.step( "Links are correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=linksResults,
            onpass="Link are correct",
            onfail="Links are incorrect" )

        main.step( "Hosts are correct" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=hostsResults,
            onpass="Hosts are correct",
            onfail="Hosts are incorrect" )

        # FIXME: move this to an ONOS state case
        main.step( "Checking ONOS nodes" )
        nodeResults = utilities.retry( main.HA.nodesCheck,
                                       False,
                                       args=[ main.activeNodes ],
                                       attempts=5 )

        utilities.assert_equals( expect=True, actual=nodeResults,
                                 onpass="Nodes check successful",
                                 onfail="Nodes check NOT successful" )
        if not nodeResults:
            for i in main.activeNodes:
                main.log.debug( "{} components not ACTIVE: \n{}".format(
                    main.CLIs[ i ].name,
                    main.CLIs[ i ].sendline( "scr:list | grep -v ACTIVE" ) ) )

        if not topoResult:
            main.cleanup()
            main.exit()

    def CASE9( self, main ):
        """
        Link s3-s28 down
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        # NOTE: You should probably run a topology check after this

        linkSleep = float( main.params[ 'timers' ][ 'LinkDiscovery' ] )

        description = "Turn off a link to ensure that Link Discovery " +\
                      "is working properly"
        main.case( description )

        main.step( "Kill Link between s3 and s28" )
        LinkDown = main.Mininet1.link( END1="s3", END2="s28", OPTION="down" )
        main.log.info( "Waiting " + str( linkSleep ) +
                       " seconds for link down to be discovered" )
        time.sleep( linkSleep )
        utilities.assert_equals( expect=main.TRUE, actual=LinkDown,
                                 onpass="Link down successful",
                                 onfail="Failed to bring link down" )
        # TODO do some sort of check here

    def CASE10( self, main ):
        """
        Link s3-s28 up
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        # NOTE: You should probably run a topology check after this

        linkSleep = float( main.params[ 'timers' ][ 'LinkDiscovery' ] )

        description = "Restore a link to ensure that Link Discovery is " + \
                      "working properly"
        main.case( description )

        main.step( "Bring link between s3 and s28 back up" )
        LinkUp = main.Mininet1.link( END1="s3", END2="s28", OPTION="up" )
        main.log.info( "Waiting " + str( linkSleep ) +
                       " seconds for link up to be discovered" )
        time.sleep( linkSleep )
        utilities.assert_equals( expect=main.TRUE, actual=LinkUp,
                                 onpass="Link up successful",
                                 onfail="Failed to bring link up" )
        # TODO do some sort of check here

    def CASE11( self, main ):
        """
        Switch Down
        """
        # NOTE: You should probably run a topology check after this
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        switchSleep = float( main.params[ 'timers' ][ 'SwitchDiscovery' ] )

        description = "Killing a switch to ensure it is discovered correctly"
        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        main.case( description )
        switch = main.params[ 'kill' ][ 'switch' ]
        switchDPID = main.params[ 'kill' ][ 'dpid' ]

        # TODO: Make this switch parameterizable
        main.step( "Kill " + switch )
        main.log.info( "Deleting " + switch )
        main.Mininet1.delSwitch( switch )
        main.log.info( "Waiting " + str( switchSleep ) +
                       " seconds for switch down to be discovered" )
        time.sleep( switchSleep )
        device = onosCli.getDevice( dpid=switchDPID )
        # Peek at the deleted switch
        main.log.warn( str( device ) )
        result = main.FALSE
        if device and device[ 'available' ] is False:
            result = main.TRUE
        utilities.assert_equals( expect=main.TRUE, actual=result,
                                 onpass="Kill switch successful",
                                 onfail="Failed to kill switch?" )

    def CASE12( self, main ):
        """
        Switch Up
        """
        # NOTE: You should probably run a topology check after this
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"
        assert ONOS1Port, "ONOS1Port not defined"
        assert ONOS2Port, "ONOS2Port not defined"
        assert ONOS3Port, "ONOS3Port not defined"
        assert ONOS4Port, "ONOS4Port not defined"
        assert ONOS5Port, "ONOS5Port not defined"
        assert ONOS6Port, "ONOS6Port not defined"
        assert ONOS7Port, "ONOS7Port not defined"

        switchSleep = float( main.params[ 'timers' ][ 'SwitchDiscovery' ] )
        switch = main.params[ 'kill' ][ 'switch' ]
        switchDPID = main.params[ 'kill' ][ 'dpid' ]
        links = main.params[ 'kill' ][ 'links' ].split()
        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        description = "Adding a switch to ensure it is discovered correctly"
        main.case( description )

        main.step( "Add back " + switch )
        main.Mininet1.addSwitch( switch, dpid=switchDPID )
        for peer in links:
            main.Mininet1.addLink( switch, peer )
        ipList = [ node.ip_address for node in main.nodes ]
        main.Mininet1.assignSwController( sw=switch, ip=ipList )
        main.log.info( "Waiting " + str( switchSleep ) +
                       " seconds for switch up to be discovered" )
        time.sleep( switchSleep )
        device = onosCli.getDevice( dpid=switchDPID )
        # Peek at the deleted switch
        main.log.warn( str( device ) )
        result = main.FALSE
        if device and device[ 'available' ]:
            result = main.TRUE
        utilities.assert_equals( expect=main.TRUE, actual=result,
                                 onpass="add switch successful",
                                 onfail="Failed to add switch?" )

    def CASE13( self, main ):
        """
        Clean up
        """
        import os
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        # printing colors to terminal
        colors = { 'cyan': '\033[96m', 'purple': '\033[95m',
                   'blue': '\033[94m', 'green': '\033[92m',
                   'yellow': '\033[93m', 'red': '\033[91m', 'end': '\033[0m' }
        main.case( "Test Cleanup" )
        main.step( "Killing tcpdumps" )
        main.Mininet2.stopTcpdump()

        testname = main.TEST
        if main.params[ 'BACKUP' ][ 'ENABLED' ] == "True":
            main.step( "Copying MN pcap and ONOS log files to test station" )
            teststationUser = main.params[ 'BACKUP' ][ 'TESTONUSER' ]
            teststationIP = main.params[ 'BACKUP' ][ 'TESTONIP' ]
            # NOTE: MN Pcap file is being saved to logdir.
            #       We scp this file as MN and TestON aren't necessarily the same vm

            # FIXME: To be replaced with a Jenkin's post script
            # TODO: Load these from params
            # NOTE: must end in /
            logFolder = "/opt/onos/log/"
            logFiles = [ "karaf.log", "karaf.log.1" ]
            # NOTE: must end in /
            for f in logFiles:
                for node in main.nodes:
                    dstName = main.logdir + "/" + node.name + "-" + f
                    main.ONOSbench.secureCopy( node.user_name, node.ip_address,
                                               logFolder + f, dstName )
            # std*.log's
            # NOTE: must end in /
            logFolder = "/opt/onos/var/"
            logFiles = [ "stderr.log", "stdout.log" ]
            # NOTE: must end in /
            for f in logFiles:
                for node in main.nodes:
                    dstName = main.logdir + "/" + node.name + "-" + f
                    main.ONOSbench.secureCopy( node.user_name, node.ip_address,
                                               logFolder + f, dstName )
        else:
            main.log.debug( "skipping saving log files" )

        main.step( "Stopping Mininet" )
        mnResult = main.Mininet1.stopNet()
        utilities.assert_equals( expect=main.TRUE, actual=mnResult,
                                 onpass="Mininet stopped",
                                 onfail="MN cleanup NOT successful" )

        main.step( "Checking ONOS Logs for errors" )
        for node in main.nodes:
            main.log.debug( "Checking logs for errors on " + node.name + ":" )
            main.log.warn( main.ONOSbench.checkLogs( node.ip_address ) )

        try:
            timerLog = open( main.logdir + "/Timers.csv", 'w' )
            # Overwrite with empty line and close
            labels = "Gossip Intents"
            data = str( gossipTime )
            timerLog.write( labels + "\n" + data )
            timerLog.close()
        except NameError as e:
            main.log.exception( e )

    def CASE14( self, main ):
        """
        start election app on all onos nodes
        """
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        main.case( "Start Leadership Election app" )
        main.step( "Install leadership election app" )
        onosCli = main.CLIs[ main.activeNodes[ 0 ] ]
        appResult = onosCli.activateApp( "org.onosproject.election" )
        utilities.assert_equals(
            expect=main.TRUE,
            actual=appResult,
            onpass="Election app installed",
            onfail="Something went wrong with installing Leadership election" )

        main.step( "Run for election on each node" )
        for i in main.activeNodes:
            main.CLIs[ i ].electionTestRun()
        time.sleep( 5 )
        activeCLIs = [ main.CLIs[ i ] for i in main.activeNodes ]
        sameResult, leaders = main.HA.consistentLeaderboards( activeCLIs )
        utilities.assert_equals(
            expect=True,
            actual=sameResult,
            onpass="All nodes see the same leaderboards",
            onfail="Inconsistent leaderboards" )

        if sameResult:
            leader = leaders[ 0 ][ 0 ]
            if main.nodes[ main.activeNodes[ 0 ] ].ip_address in leader:
                correctLeader = True
            else:
                correctLeader = False
            main.step( "First node was elected leader" )
            utilities.assert_equals(
                expect=True,
                actual=correctLeader,
                onpass="Correct leader was elected",
                onfail="Incorrect leader" )

    def CASE15( self, main ):
        """
        Check that Leadership Election is still functional
            15.1 Run election on each node
            15.2 Check that each node has the same leaders and candidates
            15.3 Find current leader and withdraw
            15.4 Check that a new node was elected leader
            15.5 Check that that new leader was the candidate of old leader
            15.6 Run for election on old leader
            15.7 Check that oldLeader is a candidate, and leader if only 1 node
            15.8 Make sure that the old leader was added to the candidate list

            old and new variable prefixes refer to data from before vs after
                withdrawl and later before withdrawl vs after re-election
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        description = "Check that Leadership Election is still functional"
        main.case( description )
        # NOTE: Need to re-run after restarts since being a canidate is not persistant

        oldLeaders = []  # list of lists of each nodes' candidates before
        newLeaders = []  # list of lists of each nodes' candidates after
        oldLeader = ''  # the old leader from oldLeaders, None if not same
        newLeader = ''  # the new leaders fron newLoeaders, None if not same
        oldLeaderCLI = None  # the CLI of the old leader used for re-electing
        expectNoLeader = False  # True when there is only one leader
        if main.numCtrls == 1:
            expectNoLeader = True

        main.step( "Run for election on each node" )
        electionResult = main.TRUE

        for i in main.activeNodes:  # run test election on each node
            if main.CLIs[ i ].electionTestRun() == main.FALSE:
                electionResult = main.FALSE
        utilities.assert_equals(
            expect=main.TRUE,
            actual=electionResult,
            onpass="All nodes successfully ran for leadership",
            onfail="At least one node failed to run for leadership" )

        if electionResult == main.FALSE:
            main.log.error(
                "Skipping Test Case because Election Test App isn't loaded" )
            main.skipCase()

        main.step( "Check that each node shows the same leader and candidates" )
        failMessage = "Nodes have different leaderboards"
        activeCLIs = [ main.CLIs[ i ] for i in main.activeNodes ]
        sameResult, oldLeaders = main.HA.consistentLeaderboards( activeCLIs )
        if sameResult:
            oldLeader = oldLeaders[ 0 ][ 0 ]
            main.log.warn( oldLeader )
        else:
            oldLeader = None
        utilities.assert_equals(
            expect=True,
            actual=sameResult,
            onpass="Leaderboards are consistent for the election topic",
            onfail=failMessage )

        main.step( "Find current leader and withdraw" )
        withdrawResult = main.TRUE
        # do some sanity checking on leader before using it
        if oldLeader is None:
            main.log.error( "Leadership isn't consistent." )
            withdrawResult = main.FALSE
        # Get the CLI of the oldLeader
        for i in main.activeNodes:
            if oldLeader == main.nodes[ i ].ip_address:
                oldLeaderCLI = main.CLIs[ i ]
                break
        else:  # FOR/ELSE statement
            main.log.error( "Leader election, could not find current leader" )
        if oldLeader:
            withdrawResult = oldLeaderCLI.electionTestWithdraw()
        utilities.assert_equals(
            expect=main.TRUE,
            actual=withdrawResult,
            onpass="Node was withdrawn from election",
            onfail="Node was not withdrawn from election" )

        main.step( "Check that a new node was elected leader" )
        failMessage = "Nodes have different leaders"
        # Get new leaders and candidates
        newLeaderResult, newLeaders = main.HA.consistentLeaderboards( activeCLIs )
        newLeader = None
        if newLeaderResult:
            if newLeaders[ 0 ][ 0 ] == 'none':
                main.log.error( "No leader was elected on at least 1 node" )
                if not expectNoLeader:
                    newLeaderResult = False
            newLeader = newLeaders[ 0 ][ 0 ]

        # Check that the new leader is not the older leader, which was withdrawn
        if newLeader == oldLeader:
            newLeaderResult = False
            main.log.error( "All nodes still see old leader: " + str( oldLeader ) +
                            " as the current leader" )
        utilities.assert_equals(
            expect=True,
            actual=newLeaderResult,
            onpass="Leadership election passed",
            onfail="Something went wrong with Leadership election" )

        main.step( "Check that that new leader was the candidate of old leader" )
        # candidates[ 2 ] should become the top candidate after withdrawl
        correctCandidateResult = main.TRUE
        if expectNoLeader:
            if newLeader == 'none':
                main.log.info( "No leader expected. None found. Pass" )
                correctCandidateResult = main.TRUE
            else:
                main.log.info( "Expected no leader, got: " + str( newLeader ) )
                correctCandidateResult = main.FALSE
        elif len( oldLeaders[ 0 ] ) >= 3:
            if newLeader == oldLeaders[ 0 ][ 2 ]:
                # correct leader was elected
                correctCandidateResult = main.TRUE
            else:
                correctCandidateResult = main.FALSE
                main.log.error( "Candidate {} was elected. {} should have had priority.".format(
                                    newLeader, oldLeaders[ 0 ][ 2 ] ) )
        else:
            main.log.warn( "Could not determine who should be the correct leader" )
            main.log.debug( oldLeaders[ 0 ] )
            correctCandidateResult = main.FALSE
        utilities.assert_equals(
            expect=main.TRUE,
            actual=correctCandidateResult,
            onpass="Correct Candidate Elected",
            onfail="Incorrect Candidate Elected" )

        main.step( "Run for election on old leader( just so everyone " +
                   "is in the hat )" )
        if oldLeaderCLI is not None:
            runResult = oldLeaderCLI.electionTestRun()
        else:
            main.log.error( "No old leader to re-elect" )
            runResult = main.FALSE
        utilities.assert_equals(
            expect=main.TRUE,
            actual=runResult,
            onpass="App re-ran for election",
            onfail="App failed to run for election" )

        main.step(
            "Check that oldLeader is a candidate, and leader if only 1 node" )
        # verify leader didn't just change
        # Get new leaders and candidates
        reRunLeaders = []
        time.sleep( 5 )  # Paremterize
        positionResult, reRunLeaders = main.HA.consistentLeaderboards( activeCLIs )

        # Check that the re-elected node is last on the candidate List
        if not reRunLeaders[ 0 ]:
            positionResult = main.FALSE
        elif oldLeader != reRunLeaders[ 0 ][ -1 ]:
            main.log.error( "Old Leader ({}) not in the proper position: {} ".format( str( oldLeader ),
                                                                                      str( reRunLeaders[ 0 ] ) ) )
            positionResult = main.FALSE
        utilities.assert_equals(
            expect=True,
            actual=positionResult,
            onpass="Old leader successfully re-ran for election",
            onfail="Something went wrong with Leadership election after " +
                   "the old leader re-ran for election" )

    def CASE16( self, main ):
        """
        Install Distributed Primitives app
        """
        import time
        assert main.numCtrls, "main.numCtrls not defined"
        assert main, "main not defined"
        assert utilities.assert_equals, "utilities.assert_equals not defined"
        assert main.CLIs, "main.CLIs not defined"
        assert main.nodes, "main.nodes not defined"

        # Variables for the distributed primitives tests
        main.pCounterName = "TestON-Partitions"
        main.pCounterValue = 0
        main.onosSet = set( [] )
        main.onosSetName = "TestON-set"

        description = "Install Primitives app"
        main.case( description )
        main.step( "Install Primitives app" )
        appName = "org.onosproject.distributedprimitives"
        node = main.activeNodes[ 0 ]
        appResults = main.CLIs[ node ].activateApp( appName )
        utilities.assert_equals( expect=main.TRUE,
                                 actual=appResults,
                                 onpass="Primitives app activated",
                                 onfail="Primitives app not activated" )
        time.sleep( 5 )  # To allow all nodes to activate

    def CASE17( self, main ):
        """
        Check for basic functionality with distributed primitives
        """
        main.HA.CASE17( main )
