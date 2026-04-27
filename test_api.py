
import requests
import json

BASE_URL = "http://localhost:8000"

def test_history():
    # 1. Login
    print("Iniciando sesión...")
    login_res = requests.post(
        f"{BASE_URL}/auth/login", 
        json={
            "email": "movil@gmail.com",
            "password": "password123"
        },
        headers={"X-Platform": "mobile"}
    )
    if login_res.status_code != 200:
        print(f"Error login: {login_res.text}")
        return
    
    token = login_res.json().get("token")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Platform": "mobile"
    }
    print("Login exitoso.")

    # 2. Get Cliente
    print("Obteniendo cliente...")
    cliente_res = requests.get(f"{BASE_URL}/clientes/mine/by-email?email=movil@gmail.com", headers=headers)
    if cliente_res.status_code != 200:
        print(f"Error cliente: {cliente_res.text}")
        return
    
    cliente_id = cliente_res.json().get("id")
    print(f"Cliente ID: {cliente_id}")

    # 3. List Solicitudes
    print("Listando solicitudes...")
    sol_res = requests.get(f"{BASE_URL}/solicitudes/?cliente_id={cliente_id}", headers=headers)
    if sol_res.status_code != 200:
        print(f"Error solicitudes: {sol_res.text}")
    else:
        sols = sol_res.json()
        print(f"Solicitudes encontradas: {len(sols)}")
        if sols:
            print("Ejemplo de solicitud:")
            print(json.dumps(sols[0], indent=2))

    # 5. List Repuestos
    print("Listando repuestos...")
    rep_res = requests.get(f"{BASE_URL}/repuestos", headers=headers)
    print(f"Status: {rep_res.status_code}")
    if rep_res.status_code == 200:
        reps = rep_res.json()
        print(f"Repuestos encontrados via API: {len(reps)}")
        if reps:
            print("Primer repuesto:")
            print(json.dumps(reps[0], indent=2))
    else:
        print(f"Error repuestos: {rep_res.text}")

if __name__ == "__main__":
    test_history()
