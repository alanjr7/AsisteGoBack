
import requests
import time

BASE_URL = "http://localhost:8000"
EMAIL = "movil@gmail.com" # Este existe por el seeder

def test_blocking():
    print(f"Probando bloqueo para {EMAIL}...")
    for i in range(1, 8):
        res = requests.post(f"{BASE_URL}/auth/login", 
                           json={"email": EMAIL, "password": "wrongpassword"},
                           headers={"X-Platform": "web"})
        print(f"Intento {i}: Status={res.status_code}, Body={res.json()}")
        if res.status_code == 403:
            print("--- BLOQUEADO ---")
            print("Intentando de nuevo mientras está bloqueado...")
            res2 = requests.post(f"{BASE_URL}/auth/login", 
                               json={"email": EMAIL, "password": "wrongpassword"},
                               headers={"X-Platform": "web"})
            print(f"Resultado post-bloqueo: Status={res2.status_code}, Body={res2.json()}")
            break

if __name__ == "__main__":
    test_blocking()
