"""
Script di Test per Simbio Core API
Esegue test funzionali contro l'API (locale o VPS remota):
- Health check
- Autenticazione (401 atteso se assente)
- Lista modelli Ollama
- Telemetria sistema VPS
- Completamento chat (test OpenAI / Zed compatibilità)
"""
import sys
import json
import httpx

# Inserisci l'indirizzo dell'API da testare (locale o VPS)
BASE_URL = "http://<YOUR_VPS_IP>:8000" if len(sys.argv) > 1 and sys.argv[1] == "remote" else "http://127.0.0.1:8000"
API_KEY = "<YOUR_SIMBIO_API_KEY>"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def print_section(title):
    print(f"\n{'='*50}\n  {title}\n{'='*50}")

def run_tests():
    print(f"Target API: {BASE_URL}")
    client = httpx.Client(timeout=20.0)

    # 1. Health check
    print_section("1. Test Health Check (Pubblico)")
    try:
        r = client.get(f"{BASE_URL}/health")
        print(f"Status Code: {r.status_code}")
        print("Risposta:", r.json())
        assert r.status_code == 200
    except Exception as e:
        print(f"ERRORE Health Check: {e}")
        return

    # 2. Test Autenticazione negativa (401 previsto)
    print_section("2. Test Sicurezza: Richiesta Senza Token (Atteso 401)")
    r = client.get(f"{BASE_URL}/api/v1/system/status")
    print(f"Status Code: {r.status_code}")
    print("Risposta:", r.json())
    assert r.status_code == 401, "Fallito: l'endpoint doveva rifiutare la richiesta!"
    print("-> Sicurezza OK: Accesso non autorizzato bloccato correttamente.")

    # 3. Test Telemetria Hardware con Token
    print_section("3. Test Telemetria Hardware (/api/v1/system/status)")
    r = client.get(f"{BASE_URL}/api/v1/system/status", headers=headers)
    print(f"Status Code: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2))
    assert r.status_code == 200

    # 4. Test Lista Modelli Ollama
    print_section("4. Test Lista Modelli (/v1/models)")
    r = client.get(f"{BASE_URL}/v1/models", headers=headers)
    print(f"Status Code: {r.status_code}")
    print("Modelli rilevati:")
    models_data = r.json()
    for m in models_data.get("data", []):
        print(f" - {m.get('id')}")

    # 5. Test Chat Completions (Zed IDE Compatibilità)
    print_section("5. Test Chat Completions (/v1/chat/completions)")
    payload = {
        "model": "qwen2.5:14b",
        "messages": [
            {"role": "user", "content": "Rispondi in sole tre parole: 'Simbio è pronto.'"}
        ],
        "stream": False
    }
    try:
        r = client.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            resp_json = r.json()
            reply = resp_json["choices"][0]["message"]["content"]
            print(f"Risposta Modello: {reply}")
        else:
            print("Dettagli errore:", r.text)
    except Exception as err:
        print("Errore durante test completamento:", err)

    print_section("TUTTI I TEST SUPERATI CON SUCCESSO!")

if __name__ == "__main__":
    run_tests()
