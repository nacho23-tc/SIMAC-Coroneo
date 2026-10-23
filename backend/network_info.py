"""Direcciones locales candidatas para abrir la web desde la misma red."""
import ipaddress
import socket

from fastapi import APIRouter, Response

router = APIRouter(prefix='/api')


@router.get('/network')
def network(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    addresses = set()
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = ipaddress.ip_address(entry[4][0])
            if address.is_private and not address.is_loopback and not address.is_link_local and not address.is_unspecified:
                addresses.add(str(address))
    except OSError:
        pass
    return {'addresses': sorted(addresses)}
