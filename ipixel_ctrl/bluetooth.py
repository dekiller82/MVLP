#!/usr/bin/env python3

# Import modules
import asyncio
from bleak import BleakScanner
from bleak import BleakClient

async def scan():
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name and d.name.startswith('LED_BLE_'):
            print(f'ADDR = {d.address} NAME = {d.name})')

async def send(target: str, payloads: list[bytes]):
    async with BleakClient(target) as client:
        _ = client.services
        for payload in payloads:
            await asyncio.sleep(0.5)
            await client.write_gatt_char('0000fa02-0000-1000-8000-00805f9b34fb', payload)
