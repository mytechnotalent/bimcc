#!/usr/bin/env python3

"""
BLE Interactive Meshtastic Chat Client 0.1.0

Usage:
    python bimcc.py "<BLE_DEVICE_ADDRESS>"

This script sends and receives text messages over the BLE interface.
It uses PyPubSub to subscribe to text messages.
"""

import sys
import time
import asyncio
from pubsub import pub
from meshtastic.ble_interface import BLEInterface, BLEClient


def custom_find_device(address):
    """
    Scans for available BLE devices without service filtering and attempts a
    case-insensitive match on the provided address. Prints discovered devices
    for debugging.

    When the Meshtastic interface attempts to locate a specific BLE device,
    this function is called to perform an unfiltered scan and compare each
    discovered device’s address (in lowercase) to the requested address.

    Parameters:
        address (str): The target BLE address to find. The function converts
                       both the discovered device addresses and this parameter
                       to lowercase for case-insensitive matching.

    Side Effects:
        - Prints a list of discovered BLE devices, including their addresses
          and names, for debugging purposes.
        - If a matching device is found, it returns immediately and no further
          devices are processed.

    Raises:
        Exception: If no device is found whose address matches (case-insensitively)
                   the specified address. The user is advised to run a BLE scan
                   (e.g., `meshtastic --ble-scan`) for troubleshooting.

    Returns:
        BLEDevice: The matching BLE device object, if found.
    """
    devices = BLEInterface.scan()
    print("Discovered Devices:")
    for d in devices:
        print(f"  Address: {d.address}, Name: {d.name}")
    addr_lower = address.lower()
    for d in devices:
        if d.address.lower() == addr_lower:
            return d
    raise Exception(f"No BLE peripheral with address '{address}' found. Try --ble-scan.")


def custom_connect(self, address=None):
    """
    Attempts to connect to a BLE device, bypassing the normal scanning process if
    a specific address is provided. If no address is given, falls back to the original
    scanning-based connect method.

    When the Meshtastic interface attempts to establish a BLE connection, this
    function creates a BLEClient (using the specified address) for a synchronous
    connection and service discovery, thereby skipping the usual scanning. If
    no address is specified, it calls the previously saved “original” connect
    function.

    Parameters:
        address (str, optional): A case-insensitive BLE address for direct connection.
                                 If omitted or None, the standard scanning-based connect
                                 logic is used instead.

    Side Effects:
        - Immediately creates a BLEClient when an address is provided, invoking a
          synchronous `connect()` call and a subsequent `discover()` for
          characteristics and services.
        - If `address` is None, performs the typical scanning-based approach.

    Raises:
        Exception: If the BLEClient’s internal `connect()` or `discover()` calls
                   fail, or if scanning fails when no address is supplied.

    Returns:
        BLEClient: The BLEClient instance representing the established connection
                   to the device.
    """
    if address:
        client = BLEClient(address, disconnected_callback=lambda _: self.close)
        client.connect()  # synchronous connect (BleakClient.connect)
        client.discover()  # discover services/characteristics
        return client
    else:
        return _original_connect(self, address)


def onReceive(packet=None, interface=None):
    """
    Callback function to process an incoming text message when the topic
    "meshtastic.receive.text" is published.

    This function accepts both 'packet' and 'interface' as optional parameters
    to avoid errors from extra keyword arguments. When the Meshtastic library
    publishes on the "meshtastic.receive.text" topic, it may include an
    'interface' argument along with 'packet'; by default, PyPubSub can raise
    errors if it encounters unexpected keywords.

    Parameters:
        packet (dict, optional): A dictionary containing data about the received
            packet. Defaults to None if no packet info is supplied.
            If present, it may include:
              - 'decoded': A dictionary that may contain a 'text' key if the
                          packet is a text message.
              - 'fromId': (Optional) The identifier of the sender. If missing,
                          defaults to "unknown".
        interface (optional): The Meshtastic interface instance that received
            the packet (provided by the publisher). Ignored here, but accepted
            to avoid 'SenderUnknownMsgDataError'.

    Side Effects:
        - If the packet contains a text message (under 'decoded.text'), it
          prints the sender ID and the message to standard output.
        - Prints a prompt ("Ch0> ") to indicate that further user
          input can be entered.

    Returns:
        None
            This function does not return anything. It processes the packet
            for display and updates the console prompt.
    """
    if not packet:
        return  # no packet data, do nothing
    decoded = packet.get("decoded", {})
    if "text" in decoded:
        sender = packet.get("fromId", "unknown")
        message = decoded["text"]
        print(f"\n{sender}: {message}")
        print("Ch0> ", end="", flush=True)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python bimcc.py <BLE_DEVICE_ADDRESS>")
        sys.exit(1)
    
    address = sys.argv[1].strip()
    print(f"Attempting to connect to BLE device at address: {address}")
    
    try:
        # creating BLEInterface automatically attempts to connect
        ble_iface = BLEInterface(address=address)
        print("Connected to BLE device!")
        # Wait a moment to stabilize
        time.sleep(2)
    except Exception as e:
        print("Error initializing BLE interface:", e)
        sys.exit(1)
    
    print("BLE Interactive Meshtastic Chat Client 0.1.0")
    print("--------------------------------------------")
    print("Type your message and press Enter to send.") 
    print("Press Ctrl+C to exit...")
    print("")

    loop = asyncio.get_running_loop()
    try:
        while True:
            # non-blocking input
            msg = await loop.run_in_executor(None, input, "Ch0> ")
            if msg:
                ble_iface.sendText(msg, channelIndex=0)
                await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ble_iface.close()
        sys.exit(0)


if __name__ == "__main__":
    BLEInterface.find_device = custom_find_device
    _original_connect = BLEInterface.connect
    BLEInterface.connect = custom_connect
    
    # subscribe to the text messages topic, using our callback that accepts both 'packet' and 'interface'
    pub.subscribe(onReceive, "meshtastic.receive.text")

    asyncio.run(main())
