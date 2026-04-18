"""
WebSocket router para notificaciones en tiempo real.
Soporta: taller, clientes, y rooms específicas de solicitudes.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
import json
import asyncio

router = APIRouter()


class ConnectionManager:
    """Gestiona conexiones WebSocket activas."""
    
    def __init__(self):
        # Conexiones por client_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Rooms: room_name -> set de client_ids
        self.rooms: Dict[str, Set[str]] = {
            "taller": set(),  # Taller puede escuchar nuevas solicitudes
            "admin": set(),
        }
    
    async def connect(self, websocket: WebSocket, client_id: str, room: Optional[str] = None):
        """Aceptar conexión y registrar cliente."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # Agregar a room específica
        if room:
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(client_id)
        
        print(f"[WebSocket] Cliente {client_id} conectado (room: {room})")
    
    def disconnect(self, client_id: str):
        """Desconectar cliente y limpiar."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # Remover de todas las rooms
        for room_name, clients in self.rooms.items():
            clients.discard(client_id)
        
        print(f"[WebSocket] Cliente {client_id} desconectado")
    
    async def send_to_client(self, client_id: str, message: dict):
        """Enviar mensaje a un cliente específico."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
                return True
            except Exception as e:
                print(f"[WebSocket] Error enviando a {client_id}: {e}")
                return False
        return False
    
    async def broadcast_to_room(self, room: str, message: dict, exclude: Optional[str] = None):
        """Enviar mensaje a todos los clientes en una room."""
        if room not in self.rooms:
            return
        
        disconnected = []
        for client_id in self.rooms[room]:
            if client_id == exclude:
                continue
            success = await self.send_to_client(client_id, message)
            if not success:
                disconnected.append(client_id)
        
        # Limpiar conexiones fallidas
        for client_id in disconnected:
            self.disconnect(client_id)
    
    async def send_to_taller(self, message: dict):
        """Enviar mensaje al taller."""
        await self.broadcast_to_room("taller", message)
    
    async def send_to_cliente(self, cliente_id: str, message: dict):
        """Enviar mensaje a un cliente específico."""
        client_ws_id = f"cliente:{cliente_id}"
        success = await self.send_to_client(client_ws_id, message)
        
        # También intentar room de solicitud si está en una
        if not success:
            await self.broadcast_to_room(f"solicitud:cliente:{cliente_id}", message)
    
    def get_client_count(self) -> int:
        """Obtener número de conexiones activas."""
        return len(self.active_connections)


# Instancia global del manager
manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    client_id: str,
    room: Optional[str] = None,
    user_type: Optional[str] = None  # "taller", "cliente", "admin"
):
    """
    Endpoint WebSocket principal.
    
    Query params:
    - room: room específica para unirse
    - user_type: tipo de usuario para routing automático
    """
    # Determinar room automáticamente por tipo
    if user_type == "taller":
        room = "taller"
    elif user_type == "cliente" and client_id.startswith("cliente:"):
        room = client_id
    
    await manager.connect(websocket, client_id, room)
    
    try:
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_text()
            message = json.loads(data)
            
            event_type = message.get("type")
            payload = message.get("payload", {})
            
            print(f"[WebSocket] Evento {event_type} de {client_id}")
            
            # Procesar eventos según tipo
            if event_type == "ping":
                await manager.send_to_client(client_id, {"type": "pong", "timestamp": payload.get("timestamp")})
            
            elif event_type == "join_room":
                new_room = payload.get("room")
                if new_room:
                    if new_room not in manager.rooms:
                        manager.rooms[new_room] = set()
                    manager.rooms[new_room].add(client_id)
                    await manager.send_to_client(client_id, {"type": "joined_room", "room": new_room})
            
            elif event_type == "leave_room":
                leave_room = payload.get("room")
                if leave_room and leave_room in manager.rooms:
                    manager.rooms[leave_room].discard(client_id)
            
            elif event_type == "subscribe_solicitud":
                # Cliente quiere escuchar una solicitud específica
                solicitud_id = payload.get("solicitud_id")
                if solicitud_id:
                    room_name = f"solicitud:{solicitud_id}"
                    if room_name not in manager.rooms:
                        manager.rooms[room_name] = set()
                    manager.rooms[room_name].add(client_id)
                    await manager.send_to_client(client_id, {
                        "type": "subscribed", 
                        "solicitud_id": solicitud_id
                    })
            
            else:
                # Broadcast a room específica si existe
                target_room = payload.get("room")
                if target_room:
                    await manager.broadcast_to_room(target_room, {
                        "type": event_type,
                        "payload": payload,
                        "sender": client_id
                    }, exclude=client_id)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"[WebSocket] Error en conexión {client_id}: {e}")
        manager.disconnect(client_id)


# Funciones helper para emitir eventos desde otros routers
def get_manager() -> ConnectionManager:
    """Obtener instancia del manager para usar en otros módulos."""
    return manager


async def notify_solicitud_nueva(solicitud: dict):
    """Notificar al taller que hay una nueva solicitud."""
    await manager.send_to_taller({
        "type": "solicitud_nueva",
        "payload": {
            "solicitud": solicitud,
            "timestamp": str(asyncio.get_event_loop().time())
        }
    })


async def notify_solicitud_aceptada(cliente_id: str, solicitud: dict):
    """Notificar al cliente que su solicitud fue aceptada."""
    await manager.send_to_cliente(cliente_id, {
        "type": "solicitud_aceptada",
        "payload": {
            "solicitud": solicitud,
            "message": "¡Tu solicitud ha sido aceptada!"
        }
    })
    
    # También notificar a la room de la solicitud
    await manager.broadcast_to_room(f"solicitud:{solicitud.get('id')}", {
        "type": "solicitud_aceptada",
        "payload": {"solicitud": solicitud}
    })


async def notify_solicitud_rechazada(cliente_id: str, solicitud_id: str, razon: str = ""):
    """Notificar al cliente que su solicitud fue rechazada."""
    await manager.send_to_cliente(cliente_id, {
        "type": "solicitud_rechazada",
        "payload": {
            "solicitud_id": solicitud_id,
            "message": razon or "El taller no pudo atender tu solicitud en este momento",
            "retry_allowed": True
        }
    })


async def notify_estado_cambiado(solicitud_id: str, nuevo_estado: str, solicitud: dict = None):
    """Notificar cambio de estado a todos los suscriptores."""
    await manager.broadcast_to_room(f"solicitud:{solicitud_id}", {
        "type": "estado_cambiado",
        "payload": {
            "solicitud_id": solicitud_id,
            "estado": nuevo_estado,
            "solicitud": solicitud
        }
    })


async def notify_chat_mensaje(solicitud_id: str, mensaje: dict):
    """Notificar nuevo mensaje de chat."""
    await manager.broadcast_to_room(f"solicitud:{solicitud_id}", {
        "type": "chat_mensaje",
        "payload": mensaje
    }, exclude=mensaje.get("sender_id"))


async def notify_mecanico_asignado(cliente_id: str, mecanico: dict, solicitud_id: str):
    """Notificar al cliente que un mecánico fue asignado."""
    await manager.send_to_cliente(cliente_id, {
        "type": "mecanico_asignado",
        "payload": {
            "solicitud_id": solicitud_id,
            "mecanico": mecanico,
            "message": f"{mecanico.get('nombre')} ha sido asignado a tu solicitud"
        }
    })


async def notify_servicio_finalizado(cliente_id: str, solicitud: dict):
    """Notificar al cliente que el servicio está listo para pago."""
    await manager.send_to_cliente(cliente_id, {
        "type": "servicio_finalizado",
        "payload": {
            "solicitud": solicitud,
            "message": "¡Servicio completado! Procede al pago"
        }
    })


async def notify_pago_confirmado(cliente_id: str, solicitud_id: str, monto: float, comision: float, total: float):
    """Notificar al cliente que el taller confirmó el monto a pagar."""
    await manager.send_to_cliente(cliente_id, {
        "type": "pago_confirmado",
        "payload": {
            "solicitud_id": solicitud_id,
            "monto": monto,
            "comision": comision,
            "total": total,
            "message": f"El servicio está listo para pagar. Total: Bs. {total}"
        }
    })
    
    # También notificar a la room de la solicitud
    await manager.broadcast_to_room(f"solicitud:{solicitud_id}", {
        "type": "pago_confirmado",
        "payload": {
            "solicitud_id": solicitud_id,
            "monto": monto,
            "comision": comision,
            "total": total
        }
    })


async def notify_pago_completado(cliente_id: str, solicitud_id: str, factura_id: str, monto: float, total: float):
    """Notificar al taller que el cliente completó el pago."""
    # Notificar al taller
    await manager.send_to_taller({
        "type": "pago_completado",
        "payload": {
            "solicitud_id": solicitud_id,
            "factura_id": factura_id,
            "cliente_id": cliente_id,
            "monto": monto,
            "total": total,
            "message": f"Pago recibido por Bs. {total}"
        }
    })
    
    # Notificar al cliente
    await manager.send_to_cliente(cliente_id, {
        "type": "pago_procesado",
        "payload": {
            "solicitud_id": solicitud_id,
            "factura_id": factura_id,
            "monto": monto,
            "total": total,
            "message": "¡Pago completado exitosamente!"
        }
    })
    
    # Notificar a la room de la solicitud
    await manager.broadcast_to_room(f"solicitud:{solicitud_id}", {
        "type": "pago_completado",
        "payload": {
            "solicitud_id": solicitud_id,
            "factura_id": factura_id,
            "monto": monto,
            "total": total
        }
    })


async def notify_pago_actualizado(solicitud_id: str, estado_pago: str, monto: float = None):
    """Notificar actualización de estado de pago."""
    await manager.broadcast_to_room(f"solicitud:{solicitud_id}", {
        "type": "pago_actualizado",
        "payload": {
            "solicitud_id": solicitud_id,
            "estado_pago": estado_pago,
            "monto": monto
        }
    })
