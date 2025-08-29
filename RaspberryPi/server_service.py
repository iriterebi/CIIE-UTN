import config
import requests
from typing import List

class ServerServices:
    baseUrl: str

    def __init__(self, baseUrl: str = config.SERVER_URL):
        self.baseUrl = baseUrl

    def get_commands(self) -> List[str]:
        url = config.SERVER_URL + '/get_data.php'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            data = response.text.strip().split('\n')
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from website: {e}")
            return []
