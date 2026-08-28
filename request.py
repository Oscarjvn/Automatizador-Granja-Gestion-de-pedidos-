import requests

url= 'http://192.168.20.27:7002/ventas'
payload= {"sucursal": "SUC019",
    "fecha_desde": "2026-08-28",
    "fecha_hasta": "2026-08-28",
    "hora_desde": "08:00",
    "hora_hasta": "09:00",
    }

try:
    # A 2-second timeout prevents your script from hanging forever
    response = requests.post(url, json=payload)
    
    # This raises an HTTPError if the response code is 4xx or 5xx
    response.raise_for_status() 

except requests.exceptions.ConnectionError as conn_err:
    print(f"Connection error occurred: {conn_err}")
    # Handle DNS failure, refused connection, or network down here

except requests.exceptions.Timeout as time_err:
    print(f"The request timed out: {time_err}")

except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred (e.g., 404 or 500): {http_err}")

except requests.exceptions.RequestException as general_err:
    print(f"An ambiguous error occurred while handling your request: {general_err}")

else:
    # This block only runs if the request succeeded perfectly
    print("Success!")
    data = response.json()
    print(data)