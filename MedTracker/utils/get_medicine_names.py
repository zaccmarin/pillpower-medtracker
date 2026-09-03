#Search algorithm to find medicine
#elements in the api response, and get the names of the medicines
#and the URL id of the medicines

def get_medicine_names(data):
    medicines = []
    for item in data.get('significantLink', []):
        # Check if item has mainEntityOfPage with Medicine in genre, which filters out non-medicine items
        
        if (item.get('mainEntityOfPage', {}).get('genre', []) 
            and 'Medicine' in item['mainEntityOfPage']['genre']):
            # Extract ID from URL - e.g '/medicines/paracetamol/' -> 'paracetamol'
            
            url = item.get('url', '')
            med_id = url.split('/')[-2] if url else None  
            
            if med_id:  
                medicines.append({
                    'name': item['name'],
                    'id': med_id
                })
            
    return medicines