#!/usr/bin/python           # This is server.py file
"""
Copyright 2016 Open Networking Foundation ( ONF )

Please refer questions to either the onos test mailing list at <onos-test@onosproject.org>,
the System Testing Plans and Results wiki page at <https://wiki.onosproject.org/x/voMg>,
or the System Testing Guide page at <https://wiki.onosproject.org/x/WYQg>

    TestON is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    ( at your option ) any later version.

    TestON is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with TestON.  If not, see <http://www.gnu.org/licenses/>.
"""
from scapy.all import *
import socket               # Import socket module
import time                 # Import Time module
import sys
import os

path = os.getcwd()
sys.path.append( 'OnosSystemTest/TestON/tests/FUNC/FUNCbgpls/dependencies' )  # Setting the path for BgpLS
from Nbdata import BgpLs

obj = BgpLs()
returnlist = obj.Constants()
peerIp = returnlist[ 0 ][ 0 ]

load_contrib( 'bgp' )
s = socket.socket()         # Create a socket object
host = peerIp  # Get local machine name
port = 179                # Reserve a port for your service.
s.bind( ( host, port ) )        # Bind to the port
pkts = rdpcap( path + "/OnosSystemTest/TestON/tests/FUNC/FUNCbgpls/dependencies/Bgpls_packets/bgpls_all.pcap" )
pkts[ 69 ][ BGPOpen ].bgp_id = peerIp

s.listen( 5 )                 # Now wait for client connection.

print( "starting Connecting to ONOS peer" )
c, addr = s.accept()     # Establish connection with client.
print 'Got connection from ONOS :', addr
c.send( str( pkts[ 69 ][ BGPHeader ] ) )  # OPEN MESSAGE
c.recv( 4096 )
c.send( str( pkts[ 71 ][ BGPHeader ] ) )  # KEEPALIVE MESSAGE
c.recv( 4096 )
c.send( str( pkts[ 72 ][ BGPHeader ] ) )   # UPDATE MESSAGES
c.send( str( pkts[ 74 ][ BGPHeader ] ) )
c.send( str( pkts[ 71 ][ BGPHeader ] ) )

while True:
    c.recv( 4096 )
    c.send( str( pkts[ 71 ][ BGPHeader ] ) )
    # c.close()                # Close the connection
