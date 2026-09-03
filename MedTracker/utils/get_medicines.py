import requests
from django.conf import settings

API_URL = settings.API
API_KEY = settings.API_KEY

#API call function
#This function takes a category as innput
#and returns a list of medicines in that category
#It uses the requests library to make a GET request to the API
def get_medicine(category):
    try: 
        headers = { "subscription-key": API_KEY, "Accept": "application/json" }
        params = {
        "category": f"{category}",
        "page": 1,
        "per-page": 100
        }
    
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()
    
    #error handling
    except requests.RequestException as e:
        return f"Error fetching medicines: {e}"
        