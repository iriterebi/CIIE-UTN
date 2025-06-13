import requests
import serial
import time

def fetch_data_from_website():
    url = 'https://ciie-lab.42web.io/get_data.php'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.text.strip().split('\n')
        return data
    else:
        print(f"Error: {response.status_code}")
        return None

def send_data_to_arduino(data, port):
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize

        for item in data:
            if item:  # Ensure the item is not empty
                ser.write((item + '\n').encode('utf-8'))
                time.sleep(1)  # Wait for a second between sending each item

        ser.close()
    except serial.SerialException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    port = 'COM6'  # Replace with the correct COM port for your Arduino

    data = fetch_data_from_website()

    if data:
        send_data_to_arduino(data, port)
        print("Data sent to Arduino successfully.")
    else:
        print("Failed to fetch data from website.")
