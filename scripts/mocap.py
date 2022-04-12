#!/usr/bin/env python3
# license removed for brevity

import asyncio
import xml.etree.ElementTree as ET
import pkg_resources
import qtm
import json
import numpy as np
import socket
import rospy
from geometry_msgs.msg import PoseStamped, Point

def create_body_index(xml_string):
    """ Extract a name to index dictionary from 6-DOF settings xml """
    xml = ET.fromstring(xml_string)

    body_to_index = {}
    for index, body in enumerate(xml.findall("*/Body/Name")):
        body_to_index[body.text.strip()] = index

    return body_to_index


def publisher_udp_main(json_file_data):
    """
    The following two lines show what is json_file_data

        json_file = open('mocap_config.json')
        json_file_data = json.load(json_file)
    """

    # IP for publisher
    HOST_UDP = json_file_data['HOST_UDP']
    # Port for publisher
    PORT_UDP = int(json_file_data['PORT_UDP'])

    server_address_udp = (HOST_UDP, PORT_UDP)
    # Create a UDP socket
    sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    return sock_udp, server_address_udp


async def main(network_config_file_name, pub):
    print("hello")
    if not rospy.is_shutdown():
        print("hello again")

        # 1 for realtime streaming, 0 for loading qtm file
        flag_realtime = 1

        # IP address for the mocap server
        IP_server = "192.168.1.122"
        print(IP_server)

        # If you want to stream recorded data in a real-time way, change json file and load it here.
        # There might be a bug about file path. Will test it later. -- Sept. 08, 2020
        file_name_qtm = "data/Demo.qtm"
        QTM_FILE = pkg_resources.resource_filename("qtm", file_name_qtm)

        # Connect to qtm
        connection = await qtm.connect(IP_server)

        # Connection failed?
        if connection is None:
            print("Failed to connect")
            return

        # Take control of qtm, context manager will automatically release control after scope end
        async with qtm.TakeControl(connection, "password"):
            if not flag_realtime:
                # Load qtm file
                await connection.load(QTM_FILE)
                # start rtfromfile
                await connection.start(rtfromfile=True)

        # Get 6-DOF settings from QTM
        xml_string = await connection.get_parameters(parameters=["6d"])

        # parser for mocap rigid bodies indexing
        body_index = create_body_index(xml_string)

        wanted_body = "pixhawk"

        def on_packet(packet):
            # Get the 6-DOF data
            bodies = packet.get_6d()[1]
            print("in on_packet")

            if wanted_body is not None and wanted_body in body_index:
                # Extract one specific body
                wanted_index = body_index[wanted_body]
                position, rotation = bodies[wanted_index]
                # You can use position and rotation here. Notice that the unit for position is mm!
                print(wanted_body)

                print("Position in numpy [meter]")
                x = position.x/1000.0
                y = position.y/1000.0
                z = position.z/1000.0
                t = rospy.Time.now()

                msg = PoseStamped()
                msg.header.stamp = t
                msg.pose.position = Point(x, y, z)

                rospy.loginfo(msg)
                pub.publish(msg)

        # Start streaming frames
        # Make sure the component matches with the data fetch function, for example: packet.get_6d() with "6d"
        # Reference: https://qualisys.github.io/qualisys_python_sdk/index.html
        print('awaiting')
        await connection.stream_frames(components=["6d"], on_packet=on_packet)

if __name__ == '__main__':
    try:
        pub = rospy.Publisher('/mavros/vision_pose/pose', PoseStamped, queue_size=10)

        rospy.init_node('talker', anonymous=True)

        network_config_file_name = 'mocap_config.json'
    
        asyncio.ensure_future(main(network_config_file_name, pub))
        asyncio.get_event_loop().run_forever()

    except rospy.ROSInterruptException:
        print("error")