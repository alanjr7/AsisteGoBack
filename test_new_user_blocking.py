
import requests
import uuid

BASE_URL = "http://localhost:8000"
# Usamos un email aleatorio para asegurar que no esté bloqueado previamente
EMAIL = f"test_{uuid.uuid4().hex[:8]}@example.com"

def test_blocking():
    # Primero registramos al usuario para que exista
    print(f"Registrando usuario {EMAIL}...")
    reg = requests.post(f"{BASE_URL}/auth/register", 
                        json={"nombre": "Test User", "email": EMAIL, "password": "password123", "tipo_usuario": "taller"})
    print(f"Registro: {reg.status_code}")

    print(f"Probando bloqueo para {EMAIL}...")
    for i in range(1, 8):
        res = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": EMAIL, "password": "wrongpassword"},
                           headers={"X-Platform": "web"})
        print(f"Intento {i}: Status={res.status_code}, Body={res.json()}")
        
        if res.status_code == 403:
            print("--- BLOQUEADO CORRECTAMENTE ---")
            break
        elif res.status_code == 429:
            print("--- RATE LIMIT (IP) ACTIVADO ---")
            break

if __name__ == "__main__":
    test_blocking()
